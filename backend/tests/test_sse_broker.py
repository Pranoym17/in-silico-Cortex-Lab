from uuid import uuid4

import pytest

from app.services.sse_broker import JobEventBroker


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
