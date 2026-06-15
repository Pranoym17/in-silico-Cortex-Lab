import pytest
from pydantic import ValidationError

from app.schemas.sse import ErrorEvent
from app.services.error_codes import is_retryable_job_error, normalize_job_error_code


def test_error_event_accepts_standard_error_codes():
    payload = ErrorEvent(
        job_id="job_1",
        code="result_storage_failed",
        message="Result could not be saved.",
        retryable=True,
    ).model_dump(mode="json")

    assert payload["code"] == "result_storage_failed"


def test_error_event_rejects_unknown_error_codes():
    with pytest.raises(ValidationError):
        ErrorEvent(job_id="job_1", code="modal_error", message="bad", retryable=True)


def test_normalize_job_error_code_maps_unknown_to_internal_error():
    assert normalize_job_error_code("timeout") == "timeout"
    assert normalize_job_error_code("modal_error") == "internal_error"
    assert normalize_job_error_code(None) == "internal_error"


def test_retry_policy_defaults_are_centralized():
    assert is_retryable_job_error("timeout") is True
    assert is_retryable_job_error("validation_failed") is False
    assert is_retryable_job_error("model_access_required") is False
    assert is_retryable_job_error("internal_error", default=False) is False
