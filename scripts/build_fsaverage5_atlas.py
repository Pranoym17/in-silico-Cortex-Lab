from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Literal


Hemisphere = Literal["left", "right"]

ATLAS_SOURCE = "freesurfer-fsaverage-aparc-nearest-to-nilearn-fsaverage5"


def normalize_region_name(*, hemisphere_prefix: str, raw_name: str | bytes) -> str:
    cleaned = raw_name.decode("utf-8") if isinstance(raw_name, bytes) else raw_name
    cleaned = cleaned.replace("_and_", "-and-").replace("_", "-")
    if cleaned.lower() in {"unknown", "corpuscallosum", "???", ""}:
        return f"{hemisphere_prefix}-Unknown"
    return f"{hemisphere_prefix}-{cleaned}"


def load_gifti_vertices(surface_path: Path):
    try:
        import nibabel as nib
    except ImportError as exc:
        raise RuntimeError("nibabel is required to read GIFTI surfaces.") from exc

    image = nib.load(str(surface_path))
    if not image.darrays:
        raise ValueError(f"{surface_path} does not contain GIFTI data arrays")
    return image.darrays[0].data


def load_freesurfer_surface_and_annotation(*, surface_path: Path, annotation_path: Path):
    try:
        from nibabel.freesurfer.io import read_annot, read_geometry
    except ImportError as exc:
        raise RuntimeError("nibabel is required to read FreeSurfer annotation files.") from exc

    vertices, _faces = read_geometry(str(surface_path))
    labels, _color_table, names = read_annot(str(annotation_path))
    return vertices, labels, names


def project_annotation_to_target(
    *,
    source_vertices,
    source_labels,
    source_names,
    target_vertices,
    hemisphere_prefix: str,
) -> list[str]:
    try:
        from scipy.spatial import cKDTree
    except ImportError as exc:
        raise RuntimeError("scipy is required to project full fsaverage labels to fsaverage5.") from exc

    _distances, source_indices = cKDTree(source_vertices).query(target_vertices, k=1)
    region_names: list[str] = []
    for source_index in source_indices:
        label = int(source_labels[int(source_index)])
        if label < 0 or label >= len(source_names):
            region_names.append(f"{hemisphere_prefix}-Unknown")
        else:
            region_names.append(normalize_region_name(hemisphere_prefix=hemisphere_prefix, raw_name=source_names[label]))
    return region_names


def build_vertex_atlas(*, left_region_names: list[str], right_region_names: list[str]) -> dict[str, str]:
    atlas = {str(index): name for index, name in enumerate(left_region_names)}
    atlas.update({str(index + len(left_region_names)): name for index, name in enumerate(right_region_names)})
    return atlas


def update_manifest_atlas_source(manifest_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["atlas"] = "desikan-killiany"
    manifest["atlas_source"] = ATLAS_SOURCE
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_projected_hemisphere(
    *,
    subjects_dir: Path,
    target_surface: Path,
    hemisphere: Hemisphere,
) -> list[str]:
    freesurfer_prefix = "lh" if hemisphere == "left" else "rh"
    display_prefix = "Left" if hemisphere == "left" else "Right"
    source_vertices, source_labels, source_names = load_freesurfer_surface_and_annotation(
        surface_path=subjects_dir / "fsaverage" / "surf" / f"{freesurfer_prefix}.pial",
        annotation_path=subjects_dir / "fsaverage" / "label" / f"{freesurfer_prefix}.aparc.annot",
    )
    target_vertices = load_gifti_vertices(target_surface)
    return project_annotation_to_target(
        source_vertices=source_vertices,
        source_labels=source_labels,
        source_names=source_names,
        target_vertices=target_vertices,
        hemisphere_prefix=display_prefix,
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build fsaverage5 Desikan-Killiany atlas labels for Cortex Lab.")
    parser.add_argument("--subjects-dir", type=Path, required=True, help="Directory containing the MNE/FreeSurfer fsaverage subject.")
    parser.add_argument("--left-gifti", type=Path, required=True, help="Left fsaverage5 GIFTI surface used by the viewer.")
    parser.add_argument("--right-gifti", type=Path, required=True, help="Right fsaverage5 GIFTI surface used by the viewer.")
    parser.add_argument("--out", type=Path, default=Path("frontend/public/brain/atlas-desikan-killiany.json"))
    parser.add_argument("--manifest", type=Path, default=Path("frontend/public/brain/mesh-manifest.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    left_region_names = build_projected_hemisphere(
        subjects_dir=args.subjects_dir,
        target_surface=args.left_gifti,
        hemisphere="left",
    )
    right_region_names = build_projected_hemisphere(
        subjects_dir=args.subjects_dir,
        target_surface=args.right_gifti,
        hemisphere="right",
    )
    write_json(args.out, build_vertex_atlas(left_region_names=left_region_names, right_region_names=right_region_names))
    update_manifest_atlas_source(args.manifest)


if __name__ == "__main__":
    main()
