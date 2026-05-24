from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


SurfaceKind = Literal["pial", "inflated", "white"]

SURFACE = "fsaverage5"
ATLAS = "desikan-killiany"
LEFT_VERTEX_OFFSET = 0
NEUTRAL_VERTEX_COLOR = (150, 150, 150, 255)


@dataclass(frozen=True)
class HemisphereAsset:
    key: Literal["left", "right"]
    freesurfer_prefix: Literal["lh", "rh"]
    display_prefix: Literal["Left", "Right"]
    surface_path: Path
    annotation_path: Path
    output_path: Path
    activation_offset: int


def build_manifest(*, left_vertex_count: int, right_vertex_count: int) -> dict[str, Any]:
    return {
        "surface": SURFACE,
        "vertex_count": left_vertex_count + right_vertex_count,
        "left_vertex_count": left_vertex_count,
        "right_vertex_count": right_vertex_count,
        "ordering": "left-then-right",
        "atlas": ATLAS,
        "gltf": {
            "left": "/brain/fsaverage5_left.gltf",
            "right": "/brain/fsaverage5_right.gltf",
        },
        "hemispheres": {
            "left": {
                "file": "/brain/fsaverage5_left.gltf",
                "vertex_count": left_vertex_count,
                "activation_offset": 0,
            },
            "right": {
                "file": "/brain/fsaverage5_right.gltf",
                "vertex_count": right_vertex_count,
                "activation_offset": left_vertex_count,
            },
        },
    }


def build_vertex_atlas(
    *,
    left_region_names: list[str],
    right_region_names: list[str],
) -> dict[str, str]:
    atlas: dict[str, str] = {}
    for index, name in enumerate(left_region_names):
        atlas[str(index)] = name
    for index, name in enumerate(right_region_names, start=len(left_region_names)):
        atlas[str(index)] = name
    return atlas


def validate_vertex_counts(
    *,
    left_vertex_count: int,
    right_vertex_count: int,
    left_label_count: int,
    right_label_count: int,
) -> None:
    if left_vertex_count != left_label_count:
        raise ValueError(f"left hemisphere has {left_vertex_count} vertices but {left_label_count} atlas labels")
    if right_vertex_count != right_label_count:
        raise ValueError(f"right hemisphere has {right_vertex_count} vertices but {right_label_count} atlas labels")


def require_inputs(paths: list[Path]) -> None:
    missing = [path for path in paths if not path.exists()]
    if missing:
        formatted = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(f"Missing required FreeSurfer input files:\n{formatted}")


def normalize_region_name(*, hemisphere_prefix: str, raw_name: str) -> str:
    cleaned = raw_name.decode("utf-8") if isinstance(raw_name, bytes) else raw_name
    cleaned = cleaned.replace("_and_", "-and-").replace("_", "-")
    if cleaned.lower() in {"unknown", "corpuscallosum", "???", ""}:
        return f"{hemisphere_prefix}-Unknown"
    return f"{hemisphere_prefix}-{cleaned}"


def load_freesurfer_geometry(surface_path: Path):
    try:
        from nibabel.freesurfer.io import read_geometry
    except ImportError as exc:
        raise RuntimeError("nibabel is required to read FreeSurfer surfaces. Install backend requirements.") from exc

    return read_geometry(str(surface_path))


def load_freesurfer_annotation(annotation_path: Path, hemisphere_prefix: str) -> list[str]:
    try:
        from nibabel.freesurfer.io import read_annot
    except ImportError as exc:
        raise RuntimeError("nibabel is required to read FreeSurfer annotations. Install backend requirements.") from exc

    labels, _color_table, names = read_annot(str(annotation_path))
    region_names: list[str] = []
    for label in labels:
        if label < 0 or label >= len(names):
            region_names.append(f"{hemisphere_prefix}-Unknown")
        else:
            region_names.append(normalize_region_name(hemisphere_prefix=hemisphere_prefix, raw_name=names[label]))
    return region_names


def export_gltf(*, vertices, faces, output_path: Path) -> None:
    try:
        import numpy as np
        import trimesh
    except ImportError as exc:
        raise RuntimeError("numpy and trimesh are required to export GLTF brain meshes. Install backend requirements.") from exc

    mesh = trimesh.Trimesh(
        vertices=np.asarray(vertices, dtype=np.float32),
        faces=np.asarray(faces, dtype=np.int64),
        process=False,
    )
    mesh.visual.vertex_colors = np.tile(
        np.asarray(NEUTRAL_VERTEX_COLOR, dtype=np.uint8),
        (len(mesh.vertices), 1),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(output_path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_hemisphere_assets(
    *,
    subjects_dir: Path,
    subject: str,
    surface_kind: SurfaceKind,
    output_dir: Path,
    left_vertex_count: int = 0,
) -> tuple[HemisphereAsset, HemisphereAsset]:
    subject_dir = subjects_dir / subject
    left = HemisphereAsset(
        key="left",
        freesurfer_prefix="lh",
        display_prefix="Left",
        surface_path=subject_dir / "surf" / f"lh.{surface_kind}",
        annotation_path=subject_dir / "label" / "lh.aparc.annot",
        output_path=output_dir / "fsaverage5_left.gltf",
        activation_offset=LEFT_VERTEX_OFFSET,
    )
    right = HemisphereAsset(
        key="right",
        freesurfer_prefix="rh",
        display_prefix="Right",
        surface_path=subject_dir / "surf" / f"rh.{surface_kind}",
        annotation_path=subject_dir / "label" / "rh.aparc.annot",
        output_path=output_dir / "fsaverage5_right.gltf",
        activation_offset=left_vertex_count,
    )
    return left, right


def convert_assets(*, subjects_dir: Path, subject: str, output_dir: Path, surface_kind: SurfaceKind) -> None:
    left_asset, right_asset = build_hemisphere_assets(
        subjects_dir=subjects_dir,
        subject=subject,
        surface_kind=surface_kind,
        output_dir=output_dir,
    )
    require_inputs(
        [
            left_asset.surface_path,
            right_asset.surface_path,
            left_asset.annotation_path,
            right_asset.annotation_path,
        ]
    )

    left_vertices, left_faces = load_freesurfer_geometry(left_asset.surface_path)
    right_vertices, right_faces = load_freesurfer_geometry(right_asset.surface_path)
    left_region_names = load_freesurfer_annotation(left_asset.annotation_path, left_asset.display_prefix)
    right_region_names = load_freesurfer_annotation(right_asset.annotation_path, right_asset.display_prefix)

    validate_vertex_counts(
        left_vertex_count=len(left_vertices),
        right_vertex_count=len(right_vertices),
        left_label_count=len(left_region_names),
        right_label_count=len(right_region_names),
    )

    export_gltf(vertices=left_vertices, faces=left_faces, output_path=left_asset.output_path)
    export_gltf(vertices=right_vertices, faces=right_faces, output_path=right_asset.output_path)
    write_json(
        output_dir / "atlas-desikan-killiany.json",
        build_vertex_atlas(left_region_names=left_region_names, right_region_names=right_region_names),
    )
    write_json(
        output_dir / "mesh-manifest.json",
        build_manifest(left_vertex_count=len(left_vertices), right_vertex_count=len(right_vertices)),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert FreeSurfer fsaverage5 meshes into Cortex Lab frontend assets.")
    parser.add_argument("--subjects-dir", type=Path, required=True, help="FreeSurfer SUBJECTS_DIR containing fsaverage5.")
    parser.add_argument("--subject", default="fsaverage5", help="FreeSurfer subject name. Defaults to fsaverage5.")
    parser.add_argument(
        "--surface",
        choices=["pial", "inflated", "white"],
        default="pial",
        help="Surface geometry to export.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("frontend/public/brain"),
        help="Output directory for GLTF, atlas, and manifest files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        convert_assets(
            subjects_dir=args.subjects_dir,
            subject=args.subject,
            output_dir=args.out,
            surface_kind=args.surface,
        )
    except Exception as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
