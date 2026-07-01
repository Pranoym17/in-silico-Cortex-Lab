import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validate_scientific_output.py"
SPEC = importlib.util.spec_from_file_location("validate_scientific_output", SCRIPT)
assert SPEC and SPEC.loader
validation = importlib.util.module_from_spec(SPEC)
sys.modules["validate_scientific_output"] = validation
SPEC.loader.exec_module(validation)


def test_landmark_validation_detects_expected_visual_activation():
    atlas = {
        index: ("Left-lateraloccipital" if index < 10_000 else "Left-precentral")
        for index in range(validation.EXPECTED_VERTICES)
    }
    activations = np.ones((2, validation.EXPECTED_VERTICES), dtype=np.float32)
    activations[:, :10_000] = 5

    result = validation.validate_landmark(activations, atlas, "visual")

    assert result.passed is True
    assert result.expected_percentile >= 0.60


def test_mesh_contract_requires_left_then_right_fsaverage5():
    atlas = {index: "Left-test" for index in range(validation.EXPECTED_VERTICES)}
    manifest = {
        "total_vertex_count": 20_484,
        "ordering": "left-then-right",
        "hemispheres": {
            "left": {"vertex_count": 10_242, "activation_offset": 0},
            "right": {"vertex_count": 10_242, "activation_offset": 10_242},
        },
    }

    assert validation.validate_mesh_contract(manifest, atlas) == []
    manifest["ordering"] = "right-then-left"
    assert "manifest ordering is not left-then-right" in validation.validate_mesh_contract(manifest, atlas)


def test_build_report_hashes_fixture_and_states_limitations(tmp_path):
    activation_path = tmp_path / "fixture.npz"
    atlas_path = tmp_path / "atlas.json"
    manifest_path = tmp_path / "manifest.json"
    matrix = np.ones((1, validation.EXPECTED_VERTICES), dtype=np.float32)
    matrix[:, :12_000] = 4
    np.savez_compressed(activation_path, activations=matrix)
    atlas_path.write_text(
        json.dumps(
            {
                str(index): ("Left-fusiform" if index < 12_000 else "Left-precentral")
                for index in range(validation.EXPECTED_VERTICES)
            }
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "total_vertex_count": 20_484,
                "ordering": "left-then-right",
                "hemispheres": {
                    "left": {"vertex_count": 10_242, "activation_offset": 0},
                    "right": {"vertex_count": 10_242, "activation_offset": 10_242},
                },
            }
        ),
        encoding="utf-8",
    )

    report = validation.build_report(activation_path, atlas_path, manifest_path, "faces")

    assert report["passed"] is True
    assert len(report["fixture"]["sha256"]) == 64
    assert "not measured fMRI" in report["limitations"]
