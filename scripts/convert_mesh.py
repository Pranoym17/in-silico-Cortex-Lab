from __future__ import annotations

import argparse
import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


SurfaceKind = Literal["pial", "inflated", "white"]

SURFACE = "fsaverage5"
ATLAS = "desikan-killiany"
LEFT_VERTEX_OFFSET = 0
NEUTRAL_VERTEX_COLOR = (150, 150, 150, 255)
COORDINATE_UNITS = "millimeters"
ORDERING_RULE = "left source vertex order, then right source vertex order"


@dataclass(frozen=True)
class HemisphereAsset:
    key: Literal["left", "right"]
    freesurfer_prefix: Literal["lh", "rh"]
    display_prefix: Literal["Left", "Right"]
    surface_path: Path
    annotation_path: Path
    output_path: Path
    activation_offset: int


def build_manifest(
    *,
    left_vertex_count: int,
    right_vertex_count: int,
    source: str | None = None,
    atlas_source: str | None = None,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "surface": SURFACE,
        "vertex_order": "left_then_right",
        "total_vertex_count": left_vertex_count + right_vertex_count,
        "vertex_count": left_vertex_count + right_vertex_count,
        "left_vertex_count": left_vertex_count,
        "right_vertex_count": right_vertex_count,
        "ordering": "left-then-right",
        "ordering_rule": ORDERING_RULE,
        "atlas": ATLAS,
        "coordinate_units": COORDINATE_UNITS,
        "gltf": {
            "left": "/brain/fsaverage5_left.gltf",
            "right": "/brain/fsaverage5_right.gltf",
        },
        "hemispheres": {
            "left": {
                "path": "/brain/fsaverage5_left.gltf",
                "file": "/brain/fsaverage5_left.gltf",
                "vertex_start": 0,
                "vertex_count": left_vertex_count,
                "activation_offset": 0,
            },
            "right": {
                "path": "/brain/fsaverage5_right.gltf",
                "file": "/brain/fsaverage5_right.gltf",
                "vertex_start": left_vertex_count,
                "vertex_count": right_vertex_count,
                "activation_offset": left_vertex_count,
            },
        },
    }
    if source is not None:
        manifest["source"] = source
    if atlas_source is not None:
        manifest["atlas_source"] = atlas_source
    return manifest


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


def load_gifti_geometry(surface_path: Path):
    try:
        import nibabel as nib
    except ImportError as exc:
        raise RuntimeError("nibabel is required to read GIFTI surfaces. Install backend requirements.") from exc

    image = nib.load(str(surface_path))
    arrays = image.darrays
    if len(arrays) < 2:
        raise ValueError(f"{surface_path} does not look like a surface GIFTI file")
    return arrays[0].data, arrays[1].data


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


def build_unknown_region_names(*, vertex_count: int, hemisphere_prefix: str) -> list[str]:
    return [f"{hemisphere_prefix}-Unknown" for _ in range(vertex_count)]


def export_gltf(*, vertices, faces, output_path: Path) -> None:
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("numpy is required to export GLTF brain meshes. Install backend requirements.") from exc

    vertex_array = np.asarray(vertices, dtype=np.float32)
    face_array = np.asarray(faces, dtype=np.uint32)
    normal_array = build_vertex_normals(vertex_array, face_array)
    color_rgb = np.asarray(NEUTRAL_VERTEX_COLOR[:3], dtype=np.float32) / 255.0
    color_array = np.tile(color_rgb, (len(vertex_array), 1)).astype(np.float32)

    position_bytes = pad4(vertex_array.tobytes())
    normal_bytes = pad4(normal_array.tobytes())
    color_bytes = pad4(color_array.tobytes())
    index_bytes = pad4(face_array.reshape(-1).tobytes())
    buffer = position_bytes + normal_bytes + color_bytes + index_bytes

    position_offset = 0
    normal_offset = position_offset + len(position_bytes)
    color_offset = normal_offset + len(normal_bytes)
    index_offset = color_offset + len(color_bytes)
    min_xyz = vertex_array.min(axis=0).astype(float).tolist()
    max_xyz = vertex_array.max(axis=0).astype(float).tolist()

    payload = {
        "asset": {"version": "2.0", "generator": "Cortex Lab fsaverage5 converter"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [
            {
                "primitives": [
                    {
                        "attributes": {"POSITION": 0, "NORMAL": 1, "COLOR_0": 2},
                        "indices": 3,
                        "mode": 4,
                    }
                ]
            }
        ],
        "buffers": [
            {
                "uri": f"data:application/octet-stream;base64,{base64.b64encode(buffer).decode('ascii')}",
                "byteLength": len(buffer),
            }
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": position_offset, "byteLength": len(position_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": normal_offset, "byteLength": len(normal_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": color_offset, "byteLength": len(color_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": index_offset, "byteLength": len(index_bytes), "target": 34963},
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": len(vertex_array),
                "type": "VEC3",
                "min": min_xyz,
                "max": max_xyz,
            },
            {"bufferView": 1, "componentType": 5126, "count": len(vertex_array), "type": "VEC3"},
            {"bufferView": 2, "componentType": 5126, "count": len(vertex_array), "type": "VEC3"},
            {
                "bufferView": 3,
                "componentType": 5125,
                "count": int(face_array.size),
                "type": "SCALAR",
                "min": [int(face_array.min())],
                "max": [int(face_array.max())],
            },
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")


def build_vertex_normals(vertices, faces):
    import numpy as np

    normals = np.zeros_like(vertices, dtype=np.float32)
    triangles = vertices[faces]
    face_normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(face_normals, axis=1)
    valid = lengths > 0
    face_normals[valid] = face_normals[valid] / lengths[valid, None]
    np.add.at(normals, faces[:, 0], face_normals)
    np.add.at(normals, faces[:, 1], face_normals)
    np.add.at(normals, faces[:, 2], face_normals)
    normal_lengths = np.linalg.norm(normals, axis=1)
    valid_normals = normal_lengths > 0
    normals[valid_normals] = normals[valid_normals] / normal_lengths[valid_normals, None]
    return normals.astype(np.float32)


def pad4(payload: bytes) -> bytes:
    return payload + (b"\x00" * ((4 - len(payload) % 4) % 4))


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


def convert_gifti_assets(*, left_surface: Path, right_surface: Path, output_dir: Path) -> None:
    require_inputs([left_surface, right_surface])

    left_vertices, left_faces = load_gifti_geometry(left_surface)
    right_vertices, right_faces = load_gifti_geometry(right_surface)
    left_region_names = build_unknown_region_names(vertex_count=len(left_vertices), hemisphere_prefix="Left")
    right_region_names = build_unknown_region_names(vertex_count=len(right_vertices), hemisphere_prefix="Right")

    validate_vertex_counts(
        left_vertex_count=len(left_vertices),
        right_vertex_count=len(right_vertices),
        left_label_count=len(left_region_names),
        right_label_count=len(right_region_names),
    )

    export_gltf(vertices=left_vertices, faces=left_faces, output_path=output_dir / "fsaverage5_left.gltf")
    export_gltf(vertices=right_vertices, faces=right_faces, output_path=output_dir / "fsaverage5_right.gltf")
    write_json(
        output_dir / "atlas-desikan-killiany.json",
        build_vertex_atlas(left_region_names=left_region_names, right_region_names=right_region_names),
    )
    write_json(
        output_dir / "mesh-manifest.json",
        build_manifest(
            left_vertex_count=len(left_vertices),
            right_vertex_count=len(right_vertices),
            source="nilearn-fsaverage5",
            atlas_source="unknown-placeholder",
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert FreeSurfer fsaverage5 meshes into Cortex Lab frontend assets.")
    parser.add_argument("--subjects-dir", type=Path, help="FreeSurfer SUBJECTS_DIR containing fsaverage5.")
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
    parser.add_argument("--left-gifti", type=Path, help="Optional left hemisphere fsaverage5 GIFTI surface.")
    parser.add_argument("--right-gifti", type=Path, help="Optional right hemisphere fsaverage5 GIFTI surface.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        if args.left_gifti or args.right_gifti:
            if not args.left_gifti or not args.right_gifti:
                raise ValueError("Both --left-gifti and --right-gifti are required for GIFTI conversion")
            convert_gifti_assets(
                left_surface=args.left_gifti,
                right_surface=args.right_gifti,
                output_dir=args.out,
            )
        else:
            if args.subjects_dir is None:
                raise ValueError("--subjects-dir is required for FreeSurfer conversion")
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
