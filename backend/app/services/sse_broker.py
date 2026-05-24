import asyncio
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import UUID


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


job_event_broker = JobEventBroker()


def get_job_event_broker() -> JobEventBroker:
    return job_event_broker
