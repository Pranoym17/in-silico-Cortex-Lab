from types import SimpleNamespace

from app.services import result_cache
from app.services.result_cache import cache_key_for_content_hash, get_cached_result, run_result_cache_identity, set_cached_result


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.deleted = []
        self.setex_calls = []

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self.setex_calls.append((key, ttl, value))
        self.values[key] = value

    def delete(self, key):
        self.deleted.append(key)
        self.values.pop(key, None)


class FailingRedis:
    def get(self, key):
        raise ConnectionError("redis down")

    def setex(self, key, ttl, value):
        raise ConnectionError("redis down")

    def delete(self, key):
        raise ConnectionError("redis down")


def test_cache_key_for_content_hash():
    assert cache_key_for_content_hash(" sha256:abc ") == "tribe:v2:sha256:abc"


def test_cache_key_includes_run_context_when_present():
    fast = cache_key_for_content_hash("sha256:abc", {"sample_rate_hz": 2, "model_name": "tribev2"})
    slow = cache_key_for_content_hash("sha256:abc", {"sample_rate_hz": 1, "model_name": "tribev2"})

    assert fast.startswith("tribe:v2:sha256:abc:")
    assert slow.startswith("tribe:v2:sha256:abc:")
    assert fast != slow


def test_whole_run_cache_identity_covers_media_timing_and_settings():
    baseline = {
        "blocks": [
            {
                "type": "audio",
                "content_hash": "sha256:audio",
                "start_ms": 0,
                "duration_ms": 1000,
                "condition": "speech",
                "mime_type": "audio/wav",
            }
        ],
        "settings": {"surface": "fsaverage5", "target_sample_rate_hz": 2},
    }
    baseline_hash, baseline_context = run_result_cache_identity(baseline, model_name="tribev2")
    changed = {**baseline, "settings": {**baseline["settings"], "target_sample_rate_hz": 1}}
    changed_hash, _ = run_result_cache_identity(changed, model_name="tribev2")

    assert baseline_hash.startswith("sha256:")
    assert baseline_hash != changed_hash
    assert baseline_context["cache_contract"] == "whole-run-v1"


def test_whole_run_cache_identity_rejects_missing_hash():
    try:
        run_result_cache_identity({"blocks": [{"type": "image"}]}, model_name="tribev2")
    except ValueError as exc:
        assert "content_hash" in str(exc)
    else:
        raise AssertionError("missing content hash must fail")


def test_set_and_get_cached_result(monkeypatch):
    fake_redis = FakeRedis()
    result_cache.get_settings.cache_clear()
    monkeypatch.setenv("RESULT_CACHE_ENABLED", "true")
    monkeypatch.setenv("RESULT_CACHE_TTL_SECONDS", "60")
    monkeypatch.setattr("app.services.result_cache._redis_client", lambda: fake_redis)

    result = SimpleNamespace(
        s3_key="results/job-1/activations.npz",
        format="npz",
        dtype="float32",
        shape=[4, 20484],
        vertex_count=20484,
        timestep_count=4,
        sample_rate_hz=2.0,
        model_name="tribev2",
        model_version="v2",
        metadata_json={"surface": "fsaverage5"},
    )

    set_cached_result("sha256:abc", result)
    cached = get_cached_result("sha256:abc")

    assert fake_redis.setex_calls[0][0] == "tribe:v2:sha256:abc"
    assert fake_redis.setex_calls[0][1] == 60
    assert cached is not None
    assert cached.s3_key == "results/job-1/activations.npz"
    assert cached.vertex_count == 20484
    result_cache.get_settings.cache_clear()


def test_get_cached_result_deletes_corrupt_cache(monkeypatch):
    fake_redis = FakeRedis()
    fake_redis.values["tribe:v2:sha256:bad"] = "{not-json"
    monkeypatch.setattr("app.services.result_cache._redis_client", lambda: fake_redis)

    cached = get_cached_result("sha256:bad")

    assert cached is None
    assert fake_redis.deleted == ["tribe:v2:sha256:bad"]


def test_get_cached_result_treats_redis_down_as_cache_miss(monkeypatch):
    monkeypatch.setattr("app.services.result_cache._redis_client", lambda: FailingRedis())

    assert get_cached_result("sha256:any") is None


def test_set_cached_result_treats_redis_down_as_nonfatal(monkeypatch):
    result_cache.get_settings.cache_clear()
    monkeypatch.setenv("RESULT_CACHE_ENABLED", "true")
    monkeypatch.setattr("app.services.result_cache._redis_client", lambda: FailingRedis())

    result = SimpleNamespace(
        s3_key="results/job-1/activations.npz",
        format="npz",
        dtype="float32",
        shape=[4, 20484],
        vertex_count=20484,
        timestep_count=4,
        sample_rate_hz=2.0,
        model_name="tribev2",
        model_version="v2",
        metadata_json={"surface": "fsaverage5"},
    )

    set_cached_result("sha256:abc", result)
    result_cache.get_settings.cache_clear()
