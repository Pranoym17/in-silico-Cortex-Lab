from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.prove_tribe_live import capture_live_proof, sanitize_event  # noqa: E402


def _spec():
    return {
        "job_id": "proof-1",
        "blocks": [{"id": "text-1", "type": "text", "payload": {"text": "hello"}}],
    }


def _events():
    activations = bytes(2 * 20_484 * 4)
    yield {"type": "warming", "job_id": "proof-1", "token": "never-store"}
    yield {
        "type": "stimulus_metadata",
        "block_id": "text-1",
        "stimulus_type": "text",
        "hrf_offset_seconds": 5.0,
        "word_timings": [{"word": "hello", "start_seconds": 0.0, "end_seconds": 0.4}],
    }
    yield {
        "type": "chunk",
        "job_id": "proof-1",
        "shape": [2, 20_484],
        "vertex_count": 20_484,
        "sample_rate_hz": 0.5,
        "activations": activations,
    }
    yield {
        "type": "complete",
        "job_id": "proof-1",
        "status": "complete",
        "timesteps": 2,
        "vertex_count": 20_484,
    }


def test_capture_live_proof_passes_and_records_sanitized_metrics():
    ticks = iter([0.0, 0.1, 0.3, 1.1, 1.2, 1.3])
    report = capture_live_proof(_spec(), lambda spec: _events(), clock=lambda: next(ticks))

    assert report["validation"]["passed"] is True
    assert report["metrics"]["warming_to_first_chunk_seconds"] == 1.0
    assert report["metrics"]["total_duration_seconds"] == 1.3
    assert report["events"][0]["token"] == "[REDACTED]"
    chunk = next(event for event in report["events"] if event["type"] == "chunk")
    assert "activations" not in chunk
    assert chunk["activation_byte_count"] == 2 * 20_484 * 4


def test_capture_live_proof_fails_wrong_vertex_count_and_missing_text_timing():
    def invalid_events():
        yield {"type": "warming"}
        yield {
            "type": "stimulus_metadata",
            "block_id": "text-1",
            "hrf_offset_seconds": 4.0,
            "word_timings": [],
        }
        yield {
            "type": "chunk",
            "shape": [1, 100],
            "vertex_count": 100,
            "sample_rate_hz": 0.5,
            "activations": bytes(400),
        }
        yield {"type": "complete", "status": "complete", "vertex_count": 100}

    ticks = iter([0.0, 0.1, 0.2, 0.3, 0.4, 0.5])
    report = capture_live_proof(_spec(), lambda spec: invalid_events(), clock=lambda: next(ticks))

    assert report["validation"]["passed"] is False
    assert report["validation"]["checks"]["activation_shape"]["passed"] is False
    assert report["validation"]["checks"]["hrf_alignment"]["passed"] is False
    assert report["validation"]["checks"]["word_timings"]["passed"] is False


def test_sanitize_event_redacts_nested_secrets():
    clean = sanitize_event(
        {"readiness": {"hf_token": "secret", "details": [{"authorization": "bearer"}]}}
    )

    assert clean["readiness"]["hf_token"] == "[REDACTED]"
    assert clean["readiness"]["details"][0]["authorization"] == "[REDACTED]"
