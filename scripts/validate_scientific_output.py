from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERTICES = 20_484
LANDMARKS = {
    "visual": {"lateraloccipital", "pericalcarine", "lingual", "cuneus"},
    "auditory": {"superiortemporal", "transversetemporal"},
    "language": {"parsopercularis", "parstriangularis", "superiortemporal"},
    "faces": {"fusiform"},
}


@dataclass(frozen=True)
class LandmarkResult:
    stimulus_class: str
    expected_regions: list[str]
    expected_mean_absolute_activation: float
    cortical_mean_absolute_activation: float
    expected_percentile: float
    passed: bool


def normalize_region(label: str) -> str:
    value = label.lower()
    for prefix in ("left-", "right-"):
        if value.startswith(prefix):
            return value.removeprefix(prefix)
    return value


def load_activation_matrix(path: Path) -> np.ndarray:
    with np.load(path, allow_pickle=False) as archive:
        if "activations" not in archive:
            raise ValueError("reference artifact is missing activations")
        matrix = np.asarray(archive["activations"], dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[1] != EXPECTED_VERTICES:
        raise ValueError(f"reference activations must have shape (timesteps, {EXPECTED_VERTICES})")
    if not np.isfinite(matrix).all():
        raise ValueError("reference activations contain non-finite values")
    return matrix


def load_atlas(path: Path) -> dict[int, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    atlas = {int(index): str(label) for index, label in raw.items()}
    if set(atlas) != set(range(EXPECTED_VERTICES)):
        raise ValueError("atlas must label every fsaverage5 vertex exactly once")
    return atlas


def validate_mesh_contract(manifest: dict[str, Any], atlas: dict[int, str]) -> list[str]:
    failures = []
    if manifest.get("total_vertex_count") != EXPECTED_VERTICES:
        failures.append("manifest total vertex count is not 20,484")
    if manifest.get("ordering") != "left-then-right":
        failures.append("manifest ordering is not left-then-right")
    hemispheres = manifest.get("hemispheres")
    if not isinstance(hemispheres, dict):
        failures.append("manifest hemispheres are missing")
    else:
        left = hemispheres.get("left", {})
        right = hemispheres.get("right", {})
        if left.get("vertex_count") != 10_242 or left.get("activation_offset") != 0:
            failures.append("left hemisphere mapping is invalid")
        if right.get("vertex_count") != 10_242 or right.get("activation_offset") != 10_242:
            failures.append("right hemisphere mapping is invalid")
    if len(atlas) != EXPECTED_VERTICES:
        failures.append("atlas size does not match fsaverage5")
    return failures


def validate_landmark(
    activations: np.ndarray,
    atlas: dict[int, str],
    stimulus_class: str,
    *,
    minimum_percentile: float = 0.60,
) -> LandmarkResult:
    expected = LANDMARKS.get(stimulus_class)
    if not expected:
        raise ValueError(f"unsupported stimulus class: {stimulus_class}")

    vertex_activation = np.mean(np.abs(activations), axis=0)
    expected_indices = [
        index for index, label in atlas.items() if normalize_region(label) in expected
    ]
    if not expected_indices:
        raise ValueError(f"atlas contains no expected regions for {stimulus_class}")

    expected_mean = float(np.mean(vertex_activation[expected_indices]))
    cortical_mean = float(np.mean(vertex_activation))
    percentile = float(np.mean(vertex_activation <= expected_mean))
    return LandmarkResult(
        stimulus_class=stimulus_class,
        expected_regions=sorted(expected),
        expected_mean_absolute_activation=expected_mean,
        cortical_mean_absolute_activation=cortical_mean,
        expected_percentile=percentile,
        passed=percentile >= minimum_percentile,
    )


def build_report(
    activation_path: Path,
    atlas_path: Path,
    manifest_path: Path,
    stimulus_class: str,
    *,
    minimum_percentile: float = 0.60,
) -> dict[str, Any]:
    activations = load_activation_matrix(activation_path)
    atlas = load_atlas(atlas_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mesh_failures = validate_mesh_contract(manifest, atlas)
    landmark = validate_landmark(
        activations,
        atlas,
        stimulus_class,
        minimum_percentile=minimum_percentile,
    )
    return {
        "schema_version": 1,
        "fixture": {
            "sha256": hashlib.sha256(activation_path.read_bytes()).hexdigest(),
            "shape": list(activations.shape),
            "stimulus_class": stimulus_class,
        },
        "mesh_contract": {
            "passed": not mesh_failures,
            "failures": mesh_failures,
            "ordering": manifest.get("ordering"),
        },
        "landmark": asdict(landmark),
        "passed": not mesh_failures and landmark.passed,
        "limitations": (
            "This is a model-output landmark check for an average synthetic subject. "
            "It is not measured fMRI, a diagnosis, or evidence about an individual."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a real TRIBE reference artifact against Cortex Lab contracts.")
    parser.add_argument("activation", type=Path)
    parser.add_argument("--stimulus-class", choices=sorted(LANDMARKS), required=True)
    parser.add_argument(
        "--atlas",
        type=Path,
        default=ROOT / "frontend" / "public" / "brain" / "atlas-desikan-killiany.json",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "frontend" / "public" / "brain" / "mesh-manifest.json",
    )
    parser.add_argument("--minimum-percentile", type=float, default=0.60)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = build_report(
        args.activation,
        args.atlas,
        args.manifest,
        args.stimulus_class,
        minimum_percentile=args.minimum_percentile,
    )
    output = args.output or Path("evidence") / "scientific" / f"{args.stimulus_class}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Scientific validation: {'PASS' if report['passed'] else 'FAIL'}")
    print(f"Report: {output}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
