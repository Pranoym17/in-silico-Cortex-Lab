"""Capture sanitized evidence from a deployed TRIBE Modal generator."""

from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

EXPECTED_VERTICES = 20_484
EXPECTED_HRF_SECONDS = 5.0
SENSITIVE_FIELDS = {"activations", "token", "secret", "authorization", "password"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(term in lowered for term in SENSITIVE_FIELDS)


def sanitize_event(event: dict[str, Any]) -> dict[str, Any]:
    """Retain contract evidence while removing payloads and likely credentials."""
    clean: dict[str, Any] = {}
    for key, value in event.items():
        if key == "activations":
            clean["activation_byte_count"] = len(value) if isinstance(value, (bytes, bytearray)) else None
        elif _is_sensitive(key):
            clean[key] = "[REDACTED]"
        elif isinstance(value, dict):
            clean[key] = sanitize_event(value)
        elif isinstance(value, list):
            clean[key] = [
                sanitize_event(item) if isinstance(item, dict) else item
                for item in value
            ]
        elif isinstance(value, (str, int, float, bool)) or value is None:
            clean[key] = value
        else:
            clean[key] = str(type(value).__name__)
    return clean


def _validate_word_timings(metadata: dict[str, Any]) -> tuple[bool, str]:
    timings = metadata.get("word_timings")
    if not isinstance(timings, list):
        return False, "word_timings is not a list"
    for index, timing in enumerate(timings):
        if not isinstance(timing, dict):
            return False, f"word timing {index} is not an object"
        if not isinstance(timing.get("word"), str) or not timing["word"].strip():
            return False, f"word timing {index} has no word"
        start = timing.get("start_seconds")
        end = timing.get("end_seconds")
        if not isinstance(start, (int, float)) or not math.isfinite(start) or start < 0:
            return False, f"word timing {index} has an invalid start"
        if end is not None and (
            not isinstance(end, (int, float)) or not math.isfinite(end) or end < start
        ):
            return False, f"word timing {index} has an invalid end"
    return True, f"{len(timings)} timing(s) structurally valid"


def validate_evidence(events: list[dict[str, Any]], spec: dict[str, Any]) -> dict[str, Any]:
    chunks = [event for event in events if event.get("type") == "chunk"]
    metadata = [event for event in events if event.get("type") == "stimulus_metadata"]
    completes = [event for event in events if event.get("type") == "complete"]
    errors = [event for event in events if event.get("type") == "error"]
    sample_rates = {event.get("sample_rate_hz") for event in chunks}

    checks: dict[str, dict[str, Any]] = {}

    def record(name: str, passed: bool, detail: str) -> None:
        checks[name] = {"passed": passed, "detail": detail}

    vertex_values = {event.get("vertex_count") for event in chunks}
    shape_valid = all(
        isinstance(event.get("shape"), list)
        and len(event["shape"]) == 2
        and event["shape"][1] == EXPECTED_VERTICES
        and event.get("vertex_count") == EXPECTED_VERTICES
        and event.get("activation_byte_count")
        == event["shape"][0] * event["shape"][1] * 4
        for event in chunks
    )
    record(
        "activation_shape",
        bool(chunks) and shape_valid,
        f"{len(chunks)} chunk(s), vertex values={sorted(str(value) for value in vertex_values)}",
    )

    rate_valid = len(sample_rates) == 1 and all(
        isinstance(rate, (int, float)) and math.isfinite(rate) and rate > 0
        for rate in sample_rates
    )
    record("sample_timing", bool(chunks) and rate_valid, f"sample rates={list(sample_rates)}")

    hrf_valid = bool(metadata) and all(
        event.get("hrf_offset_seconds") == EXPECTED_HRF_SECONDS for event in metadata
    )
    record("hrf_alignment", hrf_valid, f"{len(metadata)} metadata event(s), expected 5.0 seconds")

    timing_results = [_validate_word_timings(event) for event in metadata]
    required_word_blocks = {
        str(block.get("id"))
        for block in spec.get("blocks", [])
        if block.get("type") == "text"
    }
    metadata_by_block = {str(event.get("block_id")): event for event in metadata}
    text_has_words = all(
        block_id in metadata_by_block
        and bool(metadata_by_block[block_id].get("word_timings"))
        for block_id in required_word_blocks
    )
    word_valid = bool(metadata) and all(result[0] for result in timing_results) and text_has_words
    record(
        "word_timings",
        word_valid,
        f"structural={timing_results}; text blocks requiring timings={sorted(required_word_blocks)}",
    )

    complete_valid = (
        len(completes) == 1
        and completes[0].get("status") == "complete"
        and completes[0].get("vertex_count") == EXPECTED_VERTICES
        and not errors
    )
    record("completion", complete_valid, f"complete={len(completes)}, errors={len(errors)}")

    return {
        "passed": all(check["passed"] for check in checks.values()),
        "checks": checks,
    }


def capture_live_proof(
    spec: dict[str, Any],
    invoke: Callable[[dict[str, Any]], Iterable[dict[str, Any]]],
    *,
    clock: Callable[[], float] = time.perf_counter,
    gpu_hourly_usd: float | None = None,
) -> dict[str, Any]:
    started_at = _utc_now()
    start = clock()
    evidence: list[dict[str, Any]] = []
    warming_elapsed: float | None = None
    first_chunk_elapsed: float | None = None

    try:
        for raw_event in invoke(spec):
            elapsed = clock() - start
            event = sanitize_event(raw_event)
            event["observed_elapsed_seconds"] = round(elapsed, 6)
            evidence.append(event)
            if event.get("type") == "warming" and warming_elapsed is None:
                warming_elapsed = elapsed
            if event.get("type") == "chunk" and first_chunk_elapsed is None:
                first_chunk_elapsed = elapsed
    except Exception as exc:
        evidence.append(
            {
                "type": "harness_error",
                "error_class": type(exc).__name__,
                "message": "Invocation failed; inspect provider logs for details.",
                "observed_elapsed_seconds": round(clock() - start, 6),
            }
        )

    total = clock() - start
    metrics: dict[str, Any] = {
        "warming_to_first_chunk_seconds": (
            round(first_chunk_elapsed - warming_elapsed, 6)
            if warming_elapsed is not None and first_chunk_elapsed is not None
            else None
        ),
        "time_to_first_chunk_seconds": (
            round(first_chunk_elapsed, 6) if first_chunk_elapsed is not None else None
        ),
        "total_duration_seconds": round(total, 6),
        "estimated_gpu_seconds": round(total, 6),
        "gpu_cost_basis": "wall-clock estimate; verify billed usage in Modal dashboard",
    }
    if gpu_hourly_usd is not None:
        metrics["estimated_gpu_cost_usd"] = round(total * gpu_hourly_usd / 3600, 6)
        metrics["configured_gpu_hourly_usd"] = gpu_hourly_usd

    validation = validate_evidence(evidence, spec)
    return {
        "schema_version": 1,
        "started_at": started_at,
        "finished_at": _utc_now(),
        "target": {"job_id": spec.get("job_id")},
        "metrics": metrics,
        "validation": validation,
        "events": evidence,
    }


def invoke_modal(app_name: str, function_name: str) -> Callable[[dict[str, Any]], Iterable[dict[str, Any]]]:
    try:
        import modal
    except ImportError as exc:
        raise RuntimeError("Install inference/requirements.txt before running live proof") from exc

    function = modal.Function.from_name(app_name, function_name)

    def invoke(spec: dict[str, Any]) -> Iterable[dict[str, Any]]:
        yield from function.remote_gen(spec)

    return invoke


def _default_output() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("evidence") / "tribe-live" / f"{stamp}.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True, help="JSON run specification")
    parser.add_argument("--app", default="cortex-lab-tribe-inference")
    parser.add_argument("--function", default="run_real")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--gpu-hourly-usd", type=float, default=None)
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    if not isinstance(spec, dict):
        parser.error("spec must contain a JSON object")
    output = args.output or _default_output()
    report = capture_live_proof(
        spec,
        invoke_modal(args.app, args.function),
        gpu_hourly_usd=args.gpu_hourly_usd,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Evidence: {output}")
    print(f"Validation: {'PASS' if report['validation']['passed'] else 'FAIL'}")
    return 0 if report["validation"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
