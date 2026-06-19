from uuid import uuid4

import pytest

from app.services.sse_broker import JobEventBroker, RedisJobEventBroker


@pytest.mark.asyncio
async def test_broker_assigns_monotonic_event_ids_and_replays_history():
    broker = JobEventBroker(history_limit=10)
    job_id = uuid4()

    first = await broker.publish(job_id, "queued", {"job_id": str(job_id), "status": "queued"})
    second = await broker.publish(job_id, "progress", {"job_id": str(job_id), "completed_timesteps": 1})

    assert first.id == 1
    assert second.id == 2
    assert [event.id for event in await broker.replay(job_id)] == [1, 2]
    assert [event.id for event in await broker.replay(job_id, after_event_id=1)] == [2]


@pytest.mark.asyncio
async def test_broker_keeps_bounded_history():
    broker = JobEventBroker(history_limit=2)
    job_id = uuid4()

    await broker.publish(job_id, "queued", {"index": 1})
    await broker.publish(job_id, "progress", {"index": 2})
    await broker.publish(job_id, "complete", {"index": 3})

    replayed = await broker.replay(job_id)

    assert [event.id for event in replayed] == [2, 3]
    assert [event.data["index"] for event in replayed] == [2, 3]


@pytest.mark.asyncio
async def test_broker_subscriber_receives_replay_and_live_events():
    broker = JobEventBroker(history_limit=10)
    job_id = uuid4()
    await broker.publish(job_id, "queued", {"index": 1})

    subscription = broker.subscribe(job_id)
    replayed = await subscription.__anext__()
    live_publish = await broker.publish(job_id, "progress", {"index": 2})
    live = await subscription.__anext__()
    await subscription.aclose()

    assert replayed.event == "queued"
    assert replayed.data == {"index": 1}
    assert live is live_publish


@pytest.mark.asyncio
async def test_broker_subscriber_can_skip_replayed_events():
    broker = JobEventBroker(history_limit=10)
    job_id = uuid4()
    await broker.publish(job_id, "queued", {"index": 1})
    await broker.publish(job_id, "progress", {"index": 2})

    subscription = broker.subscribe(job_id, after_event_id=1)
    replayed = await subscription.__anext__()
    await subscription.aclose()

    assert replayed.id == 2
    assert replayed.data == {"index": 2}


class FakeAsyncRedis:
    def __init__(self):
        self.values = {}
        self.lists = {}
        self.published = []

    async def incr(self, key):
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def pipeline(self, transaction=True):
        return FakePipeline(self)

    async def lrange(self, key, start, end):
        values = self.lists.get(key, [])
        if end == -1:
            end = len(values) - 1
        return values[start : end + 1]

    def pubsub(self):
        return FakePubSub()


class FakePipeline:
    def __init__(self, client):
        self.client = client
        self.ops = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def rpush(self, key, value):
        self.ops.append(("rpush", key, value))

    def ltrim(self, key, start, end):
        self.ops.append(("ltrim", key, start, end))

    def publish(self, channel, value):
        self.ops.append(("publish", channel, value))

    async def execute(self):
        for op in self.ops:
            if op[0] == "rpush":
                _, key, value = op
                self.client.lists.setdefault(key, []).append(value)
            elif op[0] == "ltrim":
                _, key, start, end = op
                values = self.client.lists.setdefault(key, [])
                self.client.lists[key] = values[start:] if end == -1 else values[start : end + 1]
            elif op[0] == "publish":
                _, channel, value = op
                self.client.published.append((channel, value))


class FakePubSub:
    async def subscribe(self, channel):
        return None

    async def unsubscribe(self, channel):
        return None

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_redis_broker_assigns_ids_and_replays_history(monkeypatch):
    fake_redis = FakeAsyncRedis()
    monkeypatch.setattr("app.services.sse_broker.redis_async.Redis.from_url", lambda *args, **kwargs: fake_redis)
    broker = RedisJobEventBroker(history_limit=2)
    job_id = uuid4()

    first = await broker.publish(job_id, "queued", {"index": 1})
    second = await broker.publish(job_id, "progress", {"index": 2})
    third = await broker.publish(job_id, "complete", {"index": 3})

    assert [first.id, second.id, third.id] == [1, 2, 3]
    replayed = await broker.replay(job_id)
    assert [event.id for event in replayed] == [2, 3]
    assert [event.data["index"] for event in replayed] == [2, 3]
