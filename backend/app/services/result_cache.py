from typing import Any
import hashlib
import json
import logging

import redis
from pydantic import BaseModel, Field, ValidationError

from app.core.config import get_settings
from app.models.result import Result

logger = logging.getLogger(__name__)


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


def cache_key_for_content_hash(content_hash: str, context: dict[str, Any] | None = None) -> str:
    normalized = content_hash.strip()
    if not context:
        return f"tribe:v2:{normalized}"
    fingerprint = hashlib.sha256(
        json.dumps(context, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()[:32]
    return f"tribe:v2:{normalized}:{fingerprint}"


def text_result_cache_context(block: Any, settings: Any, *, model_name: str, model_version: str | None = None) -> dict[str, Any]:
    return {
        "type": getattr(block, "type", None),
        "duration_ms": getattr(block, "duration_ms", None),
        "voice": getattr(block, "voice", None),
        "settings": settings.model_dump(mode="json") if hasattr(settings, "model_dump") else settings,
        "model_name": model_name,
        "model_version": model_version,
    }


def _redis_client():
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def get_cached_result(content_hash: str, context: dict[str, Any] | None = None) -> CachedResult | None:
    if not get_settings().result_cache_enabled:
        return None

    cache_key = cache_key_for_content_hash(content_hash, context)
    try:
        raw_value = _redis_client().get(cache_key)
    except Exception as exc:
        logger.warning("cache_lookup_error", extra={"cache_key": cache_key}, exc_info=exc)
        return None

    if raw_value is None:
        logger.info("cache_lookup_miss", extra={"cache_key": cache_key})
        return None

    try:
        cached = CachedResult.model_validate_json(raw_value)
        logger.info("cache_lookup_hit", extra={"cache_key": cache_key, "s3_key": cached.s3_key})
        return cached
    except (ValidationError, ValueError, TypeError):
        logger.warning("cache_corrupt", extra={"cache_key": cache_key})
        delete_cached_result(content_hash, context)
        return None


def set_cached_result(content_hash: str, result: Result, context: dict[str, Any] | None = None) -> None:
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
    cache_key = cache_key_for_content_hash(content_hash, context)
    try:
        _redis_client().setex(
            cache_key,
            get_settings().result_cache_ttl_seconds,
            cached.model_dump_json(),
        )
    except Exception as exc:
        logger.warning("cache_write_error", extra={"cache_key": cache_key}, exc_info=exc)


def delete_cached_result(content_hash: str, context: dict[str, Any] | None = None) -> None:
    cache_key = cache_key_for_content_hash(content_hash, context)
    try:
        _redis_client().delete(cache_key)
    except Exception as exc:
        logger.warning("Result cache delete failed", extra={"cache_key": cache_key}, exc_info=exc)


def cached_result_to_metadata(cached: CachedResult) -> dict[str, Any]:
    metadata = dict(cached.metadata_json)
    metadata["cache_hit"] = True
    return metadata
