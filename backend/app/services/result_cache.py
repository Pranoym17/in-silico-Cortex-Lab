from typing import Any

import redis
from pydantic import BaseModel, Field, ValidationError

from app.core.config import get_settings
from app.models.result import Result


class CachedResult(BaseModel):
    s3_key: str = Field(min_length=1)
    format: str = "npz"
    dtype: str = "float32"
    shape: list[int]
    vertex_count: int = Field(ge=0)
    timestep_count: int = Field(ge=0)
    sample_rate_hz: float | None = None
    model_name: str = "tribev2"
    model_version: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


def cache_key_for_content_hash(content_hash: str) -> str:
    normalized = content_hash.strip()
    return f"tribe:v2:{normalized}"


def _redis_client():
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def get_cached_result(content_hash: str) -> CachedResult | None:
    if not get_settings().result_cache_enabled:
        return None

    cache_key = cache_key_for_content_hash(content_hash)
    raw_value = _redis_client().get(cache_key)
    if raw_value is None:
        return None

    try:
        return CachedResult.model_validate_json(raw_value)
    except (ValidationError, ValueError, TypeError):
        _redis_client().delete(cache_key)
        return None


def set_cached_result(content_hash: str, result: Result) -> None:
    if not get_settings().result_cache_enabled:
        return

    cached = CachedResult(
        s3_key=result.s3_key,
        format=result.format,
        dtype=result.dtype,
        shape=result.shape,
        vertex_count=result.vertex_count,
        timestep_count=result.timestep_count,
        sample_rate_hz=result.sample_rate_hz,
        model_name=result.model_name,
        model_version=result.model_version,
        metadata_json=result.metadata_json,
    )
    _redis_client().setex(
        cache_key_for_content_hash(content_hash),
        get_settings().result_cache_ttl_seconds,
        cached.model_dump_json(),
    )


def cached_result_to_metadata(cached: CachedResult) -> dict[str, Any]:
    metadata = dict(cached.metadata_json)
    metadata["cache_hit"] = True
    return metadata
