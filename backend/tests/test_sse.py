from app.services.sse import encode_sse


def test_encode_sse_uses_single_line_json_data():
    event = encode_sse("queued", {"job_id": "job_1", "status": "queued"}, event_id=1)

    assert event == 'event: queued\nid: 1\ndata: {"job_id":"job_1","status":"queued"}\n\n'

