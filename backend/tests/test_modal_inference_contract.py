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
    def __init__(self):
        self.text_paths = []
        self.audio_paths = []
        self.video_paths = []
        self.predicted_events = []

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
        return np.array([[0.0, 1.0], [2.0, 3.0]], dtype=np.float32), [{"segment": 0}]


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

    assert [event["type"] for event in events] == ["warming", "progress", "chunk", "progress", "complete"]
    assert len(model.text_paths) == 1
    assert model.text_paths[0].endswith("text-real.txt")
    assert model.predicted_events == [{"text_path": model.text_paths[0]}]
    assert events[2]["shape"] == [2, 2]
    assert events[2]["timestep_count"] == 2
    assert events[-1]["timesteps"] == 2
    assert events[-1]["vertex_count"] == 2


def test_real_tribe_stream_rejects_unsupported_image_blocks():
    model = FakeTribeModel()
    spec = {
        "blocks": [
            {
                "id": "image-real",
                "type": "image",
                "start_ms": 0,
                "duration_ms": 1000,
                "content_hash": "sha256:abc123",
                "s3_key": "uploads/image.png",
                "mime_type": "image/png",
            }
        ]
    }

    stream = tribe_inference.run_real_tribe_stream(spec, model=model, working_dir=_working_dir("image"))
    next(stream)
    next(stream)
    with pytest.raises(ValueError, match="Image blocks need a documented conversion decision"):
        next(stream)


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
    assert events[2]["type"] == "chunk"


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
