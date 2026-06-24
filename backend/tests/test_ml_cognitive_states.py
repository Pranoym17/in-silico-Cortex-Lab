from uuid import uuid4

import numpy as np
import pytest

from app.services.ml_cognitive_states import (
    block_for_timestep,
    classify_cognitive_states,
    label_for_block,
    score_from_activation,
)


def run_spec():
    return {
        "blocks": [
            {"id": "block-1", "type": "image", "condition": "faces", "start_ms": 0, "duration_ms": 1000},
            {"id": "block-2", "type": "text", "condition": "sentences", "start_ms": 1000, "duration_ms": 1000, "text": "The story made sense."},
            {"id": "block-3", "type": "audio", "condition": "music", "start_ms": 2000, "duration_ms": 1000},
        ]
    }


def test_score_from_activation_scales_mean_absolute_value():
    assert score_from_activation(np.array([0.0, 0.0], dtype="<f4")) == 0.0
    assert score_from_activation(np.array([2.0, -2.0], dtype="<f4")) == 1.0


def test_label_for_block_uses_prd_labels():
    assert label_for_block({"type": "image", "condition": "faces"}, 0.5) == "Face Processing"
    assert label_for_block({"type": "image", "condition": "houses"}, 0.5) == "Visual - Scenes"
    assert label_for_block({"type": "audio", "condition": "music"}, 0.5) == "Auditory - Music"
    assert label_for_block({"type": "audio", "condition": "speech"}, 0.5) == "Auditory - Speech"
    assert label_for_block({"type": "text", "condition": "sentences"}, 0.5) == "Language Comprehension"
    assert label_for_block({"type": "image", "condition": "objects"}, 0.5) == "Visual - Objects"
    assert label_for_block({"type": "text", "condition": "sentences"}, 0.0) == "Rest / Low Activation"


def test_block_for_timestep_finds_matching_run_spec_block():
    spec = run_spec()

    assert block_for_timestep(spec, 0, timestep_count=3, sample_rate_hz=1)["id"] == "block-1"
    assert block_for_timestep(spec, 1, timestep_count=3, sample_rate_hz=1)["id"] == "block-2"
    assert block_for_timestep(spec, 2, timestep_count=3, sample_rate_hz=1)["id"] == "block-3"


def test_classify_cognitive_states_returns_one_state_per_timestep():
    response = classify_cognitive_states(
        uuid4(),
        run_spec(),
        np.array([[1.0, -1.0], [0.5, 0.5], [2.0, -2.0]], dtype="<f4"),
        sample_rate_hz=1,
    )

    assert response.classifier_version == "rules-v1"
    assert [state.timestep for state in response.states] == [0, 1, 2]
    assert [state.label for state in response.states] == [
        "Face Processing",
        "Language Comprehension",
        "Auditory - Music",
    ]
    assert all(0 <= state.confidence <= 1 for state in response.states)
    assert all(state.label in state.scores for state in response.states)
