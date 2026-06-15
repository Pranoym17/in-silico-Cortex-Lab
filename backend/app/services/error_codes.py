from __future__ import annotations

from typing import Literal


JobErrorCode = Literal[
    "upload_failed",
    "validation_failed",
    "modal_oom",
    "timeout",
    "partial_failure",
    "cache_corrupt",
    "result_storage_failed",
    "internal_error",
    "model_access_required",
    "tribe_access_denied",
]

KNOWN_JOB_ERROR_CODES: frozenset[str] = frozenset(
    {
        "upload_failed",
        "validation_failed",
        "modal_oom",
        "timeout",
        "partial_failure",
        "cache_corrupt",
        "result_storage_failed",
        "internal_error",
        "model_access_required",
        "tribe_access_denied",
    }
)

NON_RETRYABLE_JOB_ERROR_CODES: frozenset[str] = frozenset(
    {
        "validation_failed",
        "model_access_required",
        "tribe_access_denied",
        "modal_oom",
    }
)


def normalize_job_error_code(code: str | None) -> JobErrorCode:
    candidate = (code or "").strip()
    if candidate in KNOWN_JOB_ERROR_CODES:
        return candidate  # type: ignore[return-value]
    return "internal_error"


def is_retryable_job_error(code: str | None, *, default: bool = True) -> bool:
    normalized = normalize_job_error_code(code)
    if normalized in NON_RETRYABLE_JOB_ERROR_CODES:
        return False
    if normalized == "internal_error":
        return default
    return True
