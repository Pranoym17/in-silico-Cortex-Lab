import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "convert_mesh.py"
SPEC = importlib.util.spec_from_file_location("convert_mesh", SCRIPT_PATH)
assert SPEC is not None
convert_mesh = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["convert_mesh"] = convert_mesh
SPEC.loader.exec_module(convert_mesh)


def test_build_manifest_matches_brain_asset_contract():
    manifest = convert_mesh.build_manifest(left_vertex_count=10242, right_vertex_count=10242)

    assert manifest == {
        "surface": "fsaverage5",
        "vertex_count": 20484,
        "left_vertex_count": 10242,
        "right_vertex_count": 10242,
        "ordering": "left-then-right",
        "atlas": "desikan-killiany",
        "gltf": {
            "left": "/brain/fsaverage5_left.gltf",
            "right": "/brain/fsaverage5_right.gltf",
        },
        "hemispheres": {
            "left": {
                "file": "/brain/fsaverage5_left.gltf",
                "vertex_count": 10242,
                "activation_offset": 0,
            },
            "right": {
                "file": "/brain/fsaverage5_right.gltf",
                "vertex_count": 10242,
                "activation_offset": 10242,
            },
        },
    }


def test_build_vertex_atlas_uses_global_left_then_right_indices():
    atlas = convert_mesh.build_vertex_atlas(
        left_region_names=["Left-Banks-STS", "Left-Caudal-ACC"],
        right_region_names=["Right-Banks-STS"],
    )

    assert atlas == {
        "0": "Left-Banks-STS",
        "1": "Left-Caudal-ACC",
        "2": "Right-Banks-STS",
    }


def test_validate_vertex_counts_rejects_mismatched_labels():
    with pytest.raises(ValueError, match="left hemisphere has 2 vertices but 1 atlas labels"):
        convert_mesh.validate_vertex_counts(
            left_vertex_count=2,
            right_vertex_count=2,
            left_label_count=1,
            right_label_count=2,
        )


def test_require_inputs_reports_missing_files():
    existing = Path(__file__)
    missing = Path(__file__).with_name("missing_freesurfer_fixture")

    with pytest.raises(FileNotFoundError) as exc:
        convert_mesh.require_inputs([existing, missing])

    assert str(missing) in str(exc.value)


def test_normalize_region_name_adds_hemisphere_prefix():
    assert convert_mesh.normalize_region_name(hemisphere_prefix="Left", raw_name=b"bankssts") == "Left-bankssts"
    assert convert_mesh.normalize_region_name(hemisphere_prefix="Right", raw_name="unknown") == "Right-Unknown"
