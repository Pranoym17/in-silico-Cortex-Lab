import asyncio
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from dataclasses import dataclass
import json
from typing import Any
from uuid import UUID

import redis.asyncio as redis_async

from app.core.config import get_settings


@dataclass(frozen=True)
class JobStreamEvent:
    id: int
    event: str
    data: dict[str, Any]


class JobEventBroker:
    def __init__(self, history_limit: int = 100, subscriber_queue_size: int = 100) -> None:
        self.history_limit = history_limit
        self.subscriber_queue_size = subscriber_queue_size
        self._lock = asyncio.Lock()
        self._next_event_ids: defaultdict[UUID, int] = defaultdict(lambda: 1)
        self._history: defaultdict[UUID, deque[JobStreamEvent]] = defaultdict(lambda: deque(maxlen=history_limit))
        self._subscribers: defaultdict[UUID, set[asyncio.Queue[JobStreamEvent]]] = defaultdict(set)

    async def publish(self, job_id: UUID, event: str, data: dict[str, Any]) -> JobStreamEvent:
        async with self._lock:
            event_id = self._next_event_ids[job_id]
            self._next_event_ids[job_id] += 1
            stream_event = JobStreamEvent(id=event_id, event=event, data=data)
            self._history[job_id].append(stream_event)
            subscribers = tuple(self._subscribers[job_id])

        for subscriber in subscribers:
            self._enqueue(subscriber, stream_event)

        return stream_event

    async def replay(self, job_id: UUID, after_event_id: int | None = None) -> list[JobStreamEvent]:
        async with self._lock:
            events = list(self._history[job_id])

        if after_event_id is None:
            return events
        return [event for event in events if event.id > after_event_id]

    async def subscribe(self, job_id: UUID, after_event_id: int | None = None) -> AsyncIterator[JobStreamEvent]:
        queue: asyncio.Queue[JobStreamEvent] = asyncio.Queue(maxsize=self.subscriber_queue_size)

        async with self._lock:
            replay_events = list(self._history[job_id])
            self._subscribers[job_id].add(queue)

        try:
            for event in replay_events:
                if after_event_id is None or event.id > after_event_id:
                    yield event

            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                subscribers = self._subscribers.get(job_id)
                if subscribers is not None:
                    subscribers.discard(queue)
                    if not subscribers:
                        self._subscribers.pop(job_id, None)

    def _enqueue(self, queue: asyncio.Queue[JobStreamEvent], event: JobStreamEvent) -> None:
        try:
            queue.put_nowait(event)
            return
        except asyncio.QueueFull:
            pass

        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
        queue.put_nowait(event)


class RedisJobEventBroker:
    def __init__(self, history_limit: int = 100) -> None:
        settings = get_settings()
        self.history_limit = history_limit
        self._client = redis_async.Redis.from_url(settings.redis_url, decode_responses=True)

    async def publish(self, job_id: UUID, event: str, data: dict[str, Any]) -> JobStreamEvent:
        event_id = int(await self._client.incr(self._event_id_key(job_id)))
        stream_event = JobStreamEvent(id=event_id, event=event, data=data)
        encoded = self._encode(stream_event)
        history_key = self._history_key(job_id)
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.rpush(history_key, encoded)
            pipe.ltrim(history_key, -self.history_limit, -1)
            pipe.publish(self._channel(job_id), encoded)
            await pipe.execute()
        return stream_event

    async def replay(self, job_id: UUID, after_event_id: int | None = None) -> list[JobStreamEvent]:
        raw_events = await self._client.lrange(self._history_key(job_id), 0, -1)
        events = [self._decode(raw_event) for raw_event in raw_events]
        if after_event_id is None:
            return events
        return [event for event in events if event.id > after_event_id]

    async def subscribe(self, job_id: UUID, after_event_id: int | None = None) -> AsyncIterator[JobStreamEvent]:
        for event in await self.replay(job_id, after_event_id):
            yield event

        pubsub = self._client.pubsub()
        await pubsub.subscribe(self._channel(job_id))
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                event = self._decode(str(message["data"]))
                if after_event_id is not None and event.id <= after_event_id:
                    continue
                yield event
        finally:
            await pubsub.unsubscribe(self._channel(job_id))
            await pubsub.close()

    def _encode(self, event: JobStreamEvent) -> str:
        return json.dumps({"id": event.id, "event": event.event, "data": event.data}, separators=(",", ":"))

    def _decode(self, payload: str) -> JobStreamEvent:
        decoded = json.loads(payload)
        return JobStreamEvent(id=int(decoded["id"]), event=str(decoded["event"]), data=dict(decoded["data"]))

    def _history_key(self, job_id: UUID) -> str:
        return f"cortex:sse:{job_id}:history"

    def _event_id_key(self, job_id: UUID) -> str:
        return f"cortex:sse:{job_id}:event_id"

    def _channel(self, job_id: UUID) -> str:
        return f"cortex:sse:{job_id}:channel"


job_event_broker = JobEventBroker()
redis_job_event_broker: RedisJobEventBroker | None = None


def get_job_event_broker() -> JobEventBroker | RedisJobEventBroker:
    global redis_job_event_broker
    if get_settings().sse_event_backend == "redis":
        if redis_job_event_broker is None:
            redis_job_event_broker = RedisJobEventBroker()
        return redis_job_event_broker
    return job_event_broker
