import json
from typing import Any


def encode_sse(event: str, data: dict[str, Any], event_id: int | None = None) -> str:
    if "\n" in event or "\r" in event:
        raise ValueError("SSE event names cannot contain newlines")

    lines = [f"event: {event}"]
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"data: {json.dumps(data, separators=(',', ':'))}")
    return "\n".join(lines) + "\n\n"
