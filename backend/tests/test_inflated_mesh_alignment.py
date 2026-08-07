from pathlib import Path

import numpy as np
import trimesh


ROOT = Path(__file__).resolve().parents[2]
BRAIN_DIR = ROOT / "frontend" / "public" / "brain"


def load_mesh(name: str):
    return trimesh.load(BRAIN_DIR / name, force="mesh")


def test_inflated_meshes_preserve_pial_vertex_and_triangle_order():
    for hemisphere in ("left", "right"):
        pial = load_mesh(f"fsaverage5_{hemisphere}.gltf")
        inflated = load_mesh(f"fsaverage5_{hemisphere}_inflated.gltf")

        assert len(pial.vertices) == 10_242
        assert len(inflated.vertices) == len(pial.vertices)
        assert np.array_equal(inflated.faces, pial.faces)
