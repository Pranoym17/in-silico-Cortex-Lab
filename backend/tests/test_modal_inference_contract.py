import importlib.util
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "inference" / "tribe_inference.py"
SPEC = importlib.util.spec_from_file_location("tribe_inference", SCRIPT_PATH)
assert SPEC is not None
tribe_inference = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["tribe_inference"] = tribe_inference
SPEC.loader.exec_module(tribe_inference)
WORKING_DIR = Path(__file__).resolve().parents[1] / "tmp_tribe_contract"


def _working_dir(name: str) -> Path:
    path = WORKING_DIR / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _run_spec() -> dict:
    return {
        "job_id": "job-1",
        "blocks": [
            {
                "id": "image-1",
                "type": "image",
                "start_ms": 0,
                "duration_ms": 1000,
                "content_hash": "sha256:abc123",
                "s3_key": "uploads/image.png",
                "mime_type": "image/png",
            },
            {
                "id": "text-1",
                "type": "text",
                "start_ms": 1000,
                "duration_ms": 1000,
                "content_hash": "sha256:def456",
                "text": "hello brain",
            },
        ],
        "settings": {"target_sample_rate_hz": 2},
    }


def test_fake_modal_stream_emits_replayable_contract_events():
    events = list(tribe_inference.run_fake_stream(_run_spec()))

    assert [event["type"] for event in events] == [
        "warming",
        "progress",
        "chunk",
        "progress",
        "chunk",
        "progress",
        "complete",
    ]
    assert events[-1] == {
        "type": "complete",
        "job_id": "job-1",
        "status": "complete",
        "timesteps": 2,
        "vertex_count": tribe_inference.FAKE_VERTEX_COUNT,
    }


def test_fake_modal_chunk_matches_activation_binary_contract():
    chunk = next(event for event in tribe_inference.run_fake_stream(_run_spec()) if event["type"] == "chunk")

    assert chunk["job_id"] == "job-1"
    assert chunk["block_id"] == "image-1"
    assert chunk["chunk_index"] == 0
    assert chunk["timestep_start"] == 0
    assert chunk["timestep_count"] == 1
    assert chunk["sample_rate_hz"] == 2
    assert chunk["vertex_count"] == tribe_inference.FAKE_VERTEX_COUNT
    assert chunk["dtype"] == "float32"
    assert chunk["shape"] == [1, tribe_inference.FAKE_VERTEX_COUNT]

    activations = np.frombuffer(chunk["activations"], dtype="<f4")
    assert activations.shape == (tribe_inference.FAKE_VERTEX_COUNT,)
    assert activations[0] == 0
    assert activations[-1] == tribe_inference.FAKE_VERTEX_COUNT - 1


def test_fake_modal_stream_rejects_empty_specs():
    with pytest.raises(ValueError, match="at least one block"):
        list(tribe_inference.run_fake_stream({"blocks": []}))


class FakeTribeModel:
    def __init__(self, predictions=None):
        self.text_paths = []
        self.audio_paths = []
        self.video_paths = []
        self.predicted_events = []
        self.predictions = predictions

    def get_events_dataframe(self, *, text_path=None, audio_path=None, video_path=None):
        if text_path is not None:
            self.text_paths.append(text_path)
            return {"text_path": text_path}
        if audio_path is not None:
            self.audio_paths.append(audio_path)
            return {"audio_path": audio_path}
        if video_path is not None:
            self.video_paths.append(video_path)
            return {"video_path": video_path}
        raise AssertionError("expected text_path, audio_path, or video_path")

    def predict(self, *, events):
        self.predicted_events.append(events)
        if self.predictions is not None:
            return self.predictions, [{"segment": 0}]
        return np.array([[0.0, 1.0], [2.0, 3.0]], dtype=np.float32), [{"segment": 0}]


class FakeEventFrame:
    def to_dict(self, *, orient):
        assert orient == "records"
        return [
            {"type": "Word", "word": "hello", "start": 0.25, "duration": 0.4},
            {"type": "Audio", "start": 0.0, "duration": 1.0},
        ]


def test_timing_metadata_extracts_words_and_canonical_output_mapping():
    metadata = tribe_inference._timing_metadata(
        {"id": "text-1", "type": "text", "start_ms": 1500, "duration_ms": 2000},
        FakeEventFrame(),
        [{"segment": 0}, {"segment": 1}],
        output_timestep_start=3,
        output_timestep_count=2,
        sample_rate_hz=0.5,
    )

    assert metadata["word_timings"] == [{"word": "hello", "start_seconds": 0.25, "end_seconds": 0.65}]
    assert metadata["experiment_start_ms"] == 1500
    assert metadata["experiment_duration_ms"] == 2000
    assert metadata["output_timestep_start"] == 3
    assert metadata["output_timestep_count"] == 2
    assert metadata["sample_rate_hz"] == 0.5
    assert metadata["alignment_policy"] == "concatenated-block-output-v1"


def test_real_tribe_stream_uses_official_text_prediction_flow():
    model = FakeTribeModel()
    spec = {
        "job_id": "job-real",
        "blocks": [
            {
                "id": "text-real",
                "type": "text",
                "start_ms": 0,
                "duration_ms": 1000,
                "content_hash": "sha256:abc123",
                "text": "hello cortex",
            }
        ],
        "settings": {"target_sample_rate_hz": 2},
    }

    events = list(tribe_inference.run_real_tribe_stream(spec, model=model, working_dir=_working_dir("text")))

    assert [event["type"] for event in events] == [
        "warming",
        "progress",
        "stimulus_metadata",
        "chunk",
        "progress",
        "complete",
    ]
    assert len(model.text_paths) == 1
    assert model.text_paths[0].endswith("text-real.txt")
    assert model.predicted_events == [{"text_path": model.text_paths[0]}]
    assert events[2]["hrf_offset_seconds"] == 5.0
    assert events[3]["shape"] == [2, 2]
    assert events[3]["timestep_count"] == 2
    assert events[-1]["timesteps"] == 2
    assert events[-1]["vertex_count"] == 2
    assert events[-1]["model_version"] == "facebook/tribev2"
    assert events[-1]["processing_version"] == "cortex-stimulus-v1"
    assert events[-1]["runtime_ms"] >= 0


def test_real_tribe_stream_chunks_prediction_timesteps(monkeypatch):
    monkeypatch.setenv("TRIBE_CHUNK_TIMESTEPS", "2")
    model = FakeTribeModel(predictions=np.arange(15, dtype=np.float32).reshape(5, 3))
    spec = {
        "blocks": [
            {
                "id": "text-chunked",
                "type": "text",
                "start_ms": 0,
                "duration_ms": 1000,
                "content_hash": "sha256:abc123",
                "text": "chunk me",
            }
        ]
    }

    events = list(tribe_inference.run_real_tribe_stream(spec, model=model, working_dir=_working_dir("chunked")))
    chunks = [event for event in events if event["type"] == "chunk"]

    assert [chunk["chunk_index"] for chunk in chunks] == [0, 1, 2]
    assert [chunk["timestep_start"] for chunk in chunks] == [0, 2, 4]
    assert [chunk["shape"] for chunk in chunks] == [[2, 3], [2, 3], [1, 3]]
    assert [event["completed_blocks"] for event in events if event["type"] == "progress"] == [0, 1]
    assert events[-1]["timesteps"] == 5
    assert events[-1]["vertex_count"] == 3


def test_real_tribe_stream_validates_expected_vertex_count(monkeypatch):
    monkeypatch.setenv("TRIBE_EXPECTED_VERTEX_COUNT", "4")
    model = FakeTribeModel(predictions=np.arange(6, dtype=np.float32).reshape(2, 3))
    spec = {
        "blocks": [
            {
                "id": "text-wrong-vertices",
                "type": "text",
                "start_ms": 0,
                "duration_ms": 1000,
                "content_hash": "sha256:abc123",
                "text": "wrong vertices",
            }
        ]
    }

    stream = tribe_inference.run_real_tribe_stream(spec, model=model, working_dir=_working_dir("vertices"))
    next(stream)
    next(stream)
    with pytest.raises(ValueError, match="predicted 3 vertices"):
        next(stream)


def test_check_real_tribe_config_reports_missing_tribe(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("TRIBE_CHUNK_TIMESTEPS", "4")
    monkeypatch.delenv("TRIBE_EXPECTED_VERTEX_COUNT", raising=False)

    result = tribe_inference.check_real_tribe_config({"blocks": []})

    assert result["ready"] is False
    assert "TRIBE v2 package is not installed" in result["blockers"]
    assert "HF_TOKEN is not set; official TRIBE text inference may need gated LLaMA access" in result["warnings"]
    assert result["checks"]["chunk_timesteps_valid"] is True


def test_check_real_tribe_config_requires_s3_env_for_s3_media(monkeypatch):
    monkeypatch.setattr(tribe_inference.importlib.util, "find_spec", lambda name: object() if name == "tribev2" else None)
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    spec = {
        "blocks": [
            {
                "id": "audio-s3",
                "type": "audio",
                "s3_key": "uploads/audio.wav",
                "mime_type": "audio/wav",
            }
        ]
    }

    result = tribe_inference.check_real_tribe_config(spec)

    assert result["ready"] is False
    assert "S3_BUCKET_NAME is required for S3-backed audio/video blocks" in result["blockers"]
    assert "AWS_REGION is required for S3-backed audio/video blocks" in result["blockers"]
    assert result["checks"]["requires_s3_materialization"] is True


def test_check_real_tribe_config_passes_for_local_media_when_dependencies_are_present(monkeypatch):
    monkeypatch.setattr(tribe_inference.importlib.util, "find_spec", lambda name: object() if name == "tribev2" else None)
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    monkeypatch.setenv("TRIBE_CHUNK_TIMESTEPS", "4")
    monkeypatch.setenv("TRIBE_EXPECTED_VERTEX_COUNT", "20484")
    spec = {
        "blocks": [
            {
                "id": "audio-local",
                "type": "audio",
                "local_path": "C:/tmp/audio.wav",
                "mime_type": "audio/wav",
            }
        ]
    }

    result = tribe_inference.check_real_tribe_config(spec)

    assert result["ready"] is True
    assert result["blockers"] == []
    assert result["checks"]["expected_vertex_count_valid"] is True


def test_configured_stream_real_mode_emits_readiness_error(monkeypatch):
    monkeypatch.setenv("TRIBE_INFERENCE_MODE", "real")
    monkeypatch.setattr(
        tribe_inference,
        "check_real_tribe_config",
        lambda spec: {
            "ready": False,
            "blockers": ["TRIBE v2 package is not installed"],
            "warnings": [],
            "checks": {},
        },
    )

    events = list(tribe_inference.run_configured_stream({"job_id": "job-not-ready", "blocks": [{"id": "b1"}]}))

    assert events == [
        {
            "type": "error",
            "job_id": "job-not-ready",
            "code": "tribe_not_ready",
            "message": "TRIBE v2 package is not installed",
            "retryable": False,
            "readiness": {
                "ready": False,
                "blockers": ["TRIBE v2 package is not installed"],
                "warnings": [],
                "checks": {},
            },
        }
    ]


def test_configured_stream_real_mode_uses_real_stream_when_ready(monkeypatch):
    monkeypatch.setenv("TRIBE_INFERENCE_MODE", "real")
    monkeypatch.setattr(
        tribe_inference,
        "check_real_tribe_config",
        lambda spec: {
            "ready": True,
            "blockers": [],
            "warnings": [],
            "checks": {},
        },
    )

    def fake_real_stream(spec):
        yield {"type": "complete", "job_id": spec["job_id"], "status": "complete", "timesteps": 1, "vertex_count": 2}

    monkeypatch.setattr(tribe_inference, "run_real_tribe_stream", fake_real_stream)

    events = list(tribe_inference.run_configured_stream({"job_id": "job-ready", "blocks": [{"id": "b1"}]}))

    assert events == [
        {"type": "complete", "job_id": "job-ready", "status": "complete", "timesteps": 1, "vertex_count": 2}
    ]


def test_configured_stream_real_mode_maps_gated_hf_errors(monkeypatch):
    monkeypatch.setenv("TRIBE_INFERENCE_MODE", "real")
    monkeypatch.setattr(
        tribe_inference,
        "check_real_tribe_config",
        lambda spec: {
            "ready": True,
            "blockers": [],
            "warnings": [],
            "checks": {},
        },
    )

    def fake_real_stream(spec):
        yield {"type": "warming", "job_id": spec["job_id"], "reason": "tribe_model_loading", "estimated_seconds": 120}
        raise OSError(
            "You are trying to access a gated repo. Cannot access gated repo for url "
            "https://huggingface.co/meta-llama/Llama-3.2-3B/resolve/main/config.json. "
            "Access to model meta-llama/Llama-3.2-3B is restricted and you are not in the authorized list."
        )

    monkeypatch.setattr(tribe_inference, "run_real_tribe_stream", fake_real_stream)

    events = list(tribe_inference.run_configured_stream({"job_id": "job-gated", "blocks": [{"id": "b1"}]}))

    assert events == [
        {"type": "warming", "job_id": "job-gated", "reason": "tribe_model_loading", "estimated_seconds": 120},
        {
            "type": "error",
            "code": "model_access_required",
            "message": (
                "Model access is required for meta-llama/Llama-3.2-3B. Request/accept access on Hugging Face, "
                "then retry this run."
            ),
            "retryable": False,
            "details": {
                "provider": "huggingface",
                "repo_id": "meta-llama/Llama-3.2-3B",
                "error_type": "OSError",
            },
            "job_id": "job-gated",
        },
    ]


def test_classify_real_tribe_error_maps_generic_hf_403():
    result = tribe_inference.classify_real_tribe_error(
        RuntimeError("403 Client Error from https://huggingface.co/facebook/tribev2")
    )

    assert result == {
        "type": "error",
        "code": "tribe_access_denied",
        "message": "Hugging Face denied access to a model required by TRIBE v2.",
        "retryable": False,
        "details": {
            "provider": "huggingface",
            "error_type": "RuntimeError",
        },
    }


def test_real_tribe_stream_converts_image_to_supported_video(monkeypatch):
    model = FakeTribeModel()
    working_dir = _working_dir("image")
    image_path = working_dir / "stimulus.png"
    image_path.write_bytes(b"png")
    conversions = []

    def fake_convert_image_to_video(source, destination, *, duration_ms):
        conversions.append((source, destination, duration_ms))
        destination.write_bytes(b"mp4")
        return destination

    monkeypatch.setattr(tribe_inference, "convert_image_to_video", fake_convert_image_to_video)
    spec = {
        "blocks": [
            {
                "id": "image-real",
                "type": "image",
                "start_ms": 0,
                "duration_ms": 1000,
                "content_hash": "sha256:abc123",
                "local_path": str(image_path),
                "mime_type": "image/png",
            }
        ]
    }

    events = list(tribe_inference.run_real_tribe_stream(spec, model=model, working_dir=working_dir))

    assert conversions == [(image_path, working_dir / "inputs" / "image-real.mp4", 1000)]
    assert model.video_paths == [str(working_dir / "inputs" / "image-real.mp4")]
    assert events[3]["type"] == "chunk"


def test_real_tribe_stream_uses_model_repetition_time_for_sample_rate():
    model = FakeTribeModel()
    model.data = type("FakeData", (), {"TR": 2.0})()
    working_dir = _working_dir("sample-rate")
    text_path = "sample rate"
    spec = {
        "blocks": [
            {
                "id": "text-rate",
                "type": "text",
                "start_ms": 0,
                "duration_ms": 1000,
                "content_hash": "sha256:abc123",
                "text": text_path,
            }
        ],
        "settings": {"target_sample_rate_hz": 2},
    }

    events = list(tribe_inference.run_real_tribe_stream(spec, model=model, working_dir=working_dir))
    chunk = next(event for event in events if event["type"] == "chunk")

    assert chunk["sample_rate_hz"] == 0.5


def test_real_tribe_stream_uses_official_audio_path_flow():
    model = FakeTribeModel()
    audio_path = _working_dir("audio") / "stimulus.wav"
    audio_path.write_bytes(b"RIFF")
    spec = {
        "blocks": [
            {
                "id": "audio-real",
                "type": "audio",
                "start_ms": 0,
                "duration_ms": 1000,
                "content_hash": "sha256:abc123",
                "local_path": str(audio_path),
                "mime_type": "audio/wav",
            }
        ],
        "settings": {"target_sample_rate_hz": 2},
    }

    events = list(tribe_inference.run_real_tribe_stream(spec, model=model, working_dir=_working_dir("audio-work")))

    assert model.audio_paths == [str(audio_path)]
    assert model.predicted_events == [{"audio_path": str(audio_path)}]
    assert events[3]["type"] == "chunk"


def test_real_tribe_stream_materializes_s3_audio(monkeypatch):
    model = FakeTribeModel()
    downloads = []

    def fake_download_s3_object(*, bucket_name, key, destination):
        downloads.append((bucket_name, key, destination))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"RIFF")
        return destination

    monkeypatch.setenv("S3_BUCKET_NAME", "cortexlab-test")
    monkeypatch.setattr(tribe_inference, "download_s3_object", fake_download_s3_object)
    spec = {
        "blocks": [
            {
                "id": "audio-s3",
                "type": "audio",
                "start_ms": 0,
                "duration_ms": 1000,
                "content_hash": "sha256:abc123",
                "s3_key": "uploads/audio.wav",
                "mime_type": "audio/wav",
            }
        ]
    }

    list(tribe_inference.run_real_tribe_stream(spec, model=model, working_dir=_working_dir("s3-audio")))

    assert len(downloads) == 1
    assert downloads[0][0] == "cortexlab-test"
    assert downloads[0][1] == "uploads/audio.wav"
    assert downloads[0][2].name == "audio-s3.wav"
    assert model.audio_paths == [str(downloads[0][2])]


def test_real_tribe_stream_converts_browser_recording(monkeypatch):
    model = FakeTribeModel()
    working_dir = _working_dir("webm-audio")
    recording_path = working_dir / "recording.webm"
    recording_path.write_bytes(b"webm")
    conversions = []

    def fake_convert_audio_for_tribe(source, destination):
        conversions.append((source, destination))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"RIFF")
        return destination

    monkeypatch.setattr(tribe_inference, "convert_audio_for_tribe", fake_convert_audio_for_tribe)
    spec = {
        "blocks": [
            {
                "id": "recording",
                "type": "audio",
                "start_ms": 0,
                "duration_ms": 1000,
                "content_hash": "sha256:recording",
                "local_path": str(recording_path),
                "mime_type": "audio/webm",
            }
        ]
    }

    list(tribe_inference.run_real_tribe_stream(spec, model=model, working_dir=working_dir))

    converted = working_dir / "inputs" / "recording-tribe.wav"
    assert conversions == [(recording_path, converted)]
    assert model.audio_paths == [str(converted)]
