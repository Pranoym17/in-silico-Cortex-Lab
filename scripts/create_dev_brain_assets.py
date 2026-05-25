from __future__ import annotations

import base64
import json
import struct
from pathlib import Path
from typing import Any


LEFT_VERTICES = [
    (-1.0, -0.8, 0.0),
    (-1.4, -0.4, 0.3),
    (-1.2, 0.0, -0.2),
    (-1.5, 0.4, 0.2),
    (-1.0, 0.8, -0.1),
    (-0.6, 0.4, 0.25),
    (-0.8, 0.0, -0.3),
    (-0.5, -0.5, 0.1),
]

RIGHT_VERTICES = [(-x, y, z) for x, y, z in LEFT_VERTICES]

FACES = [
    (0, 1, 7),
    (1, 2, 6),
    (1, 6, 7),
    (2, 3, 5),
    (2, 5, 6),
    (3, 4, 5),
    (5, 6, 7),
    (1, 2, 3),
]

REGIONS = {
    "left": [
        "Left-Banks-STS",
        "Left-Caudal-ACC",
        "Left-Insula",
        "Left-Lateral-Occipital",
        "Left-Fusiform",
        "Left-Superior-Temporal",
        "Left-Precuneus",
        "Left-Unknown",
    ],
    "right": [
        "Right-Banks-STS",
        "Right-Caudal-ACC",
        "Right-Insula",
        "Right-Lateral-Occipital",
        "Right-Fusiform",
        "Right-Superior-Temporal",
        "Right-Precuneus",
        "Right-Unknown",
    ],
}


def _pack_floats(values: list[tuple[float, float, float]]) -> bytes:
    return b"".join(struct.pack("<fff", *item) for item in values)


def _pack_colors(count: int) -> bytes:
    return b"".join(struct.pack("<fff", 0.58, 0.60, 0.62) for _ in range(count))


def _pack_indices(faces: list[tuple[int, int, int]]) -> bytes:
    return b"".join(struct.pack("<HHH", *face) for face in faces)


def _pad4(payload: bytes) -> bytes:
    return payload + (b"\x00" * ((4 - len(payload) % 4) % 4))


def build_gltf(vertices: list[tuple[float, float, float]]) -> dict[str, Any]:
    positions = _pad4(_pack_floats(vertices))
    normals = _pad4(_pack_floats([(0.0, 0.0, 1.0) for _ in vertices]))
    colors = _pad4(_pack_colors(len(vertices)))
    indices = _pad4(_pack_indices(FACES))
    buffer = positions + normals + colors + indices

    position_offset = 0
    normal_offset = len(positions)
    color_offset = normal_offset + len(normals)
    index_offset = color_offset + len(colors)
    min_xyz = [min(vertex[axis] for vertex in vertices) for axis in range(3)]
    max_xyz = [max(vertex[axis] for vertex in vertices) for axis in range(3)]

    return {
        "asset": {"version": "2.0", "generator": "Cortex Lab dev brain asset generator"},
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
            {"buffer": 0, "byteOffset": position_offset, "byteLength": len(positions), "target": 34962},
            {"buffer": 0, "byteOffset": normal_offset, "byteLength": len(normals), "target": 34962},
            {"buffer": 0, "byteOffset": color_offset, "byteLength": len(colors), "target": 34962},
            {"buffer": 0, "byteOffset": index_offset, "byteLength": len(indices), "target": 34963},
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": len(vertices),
                "type": "VEC3",
                "min": min_xyz,
                "max": max_xyz,
            },
            {"bufferView": 1, "componentType": 5126, "count": len(vertices), "type": "VEC3"},
            {"bufferView": 2, "componentType": 5126, "count": len(vertices), "type": "VEC3"},
            {"bufferView": 3, "componentType": 5123, "count": len(FACES) * 3, "type": "SCALAR"},
        ],
    }


def build_manifest() -> dict[str, Any]:
    left_count = len(LEFT_VERTICES)
    right_count = len(RIGHT_VERTICES)
    return {
        "source": "dev-fixture",
        "surface": "fsaverage5",
        "vertex_count": left_count + right_count,
        "left_vertex_count": left_count,
        "right_vertex_count": right_count,
        "ordering": "left-then-right",
        "atlas": "desikan-killiany",
        "gltf": {
            "left": "/brain/fsaverage5_left.gltf",
            "right": "/brain/fsaverage5_right.gltf",
        },
        "hemispheres": {
            "left": {"file": "/brain/fsaverage5_left.gltf", "vertex_count": left_count, "activation_offset": 0},
            "right": {
                "file": "/brain/fsaverage5_right.gltf",
                "vertex_count": right_count,
                "activation_offset": left_count,
            },
        },
    }


def build_atlas() -> dict[str, str]:
    atlas = {str(index): name for index, name in enumerate(REGIONS["left"])}
    atlas.update({str(index + len(LEFT_VERTICES)): name for index, name in enumerate(REGIONS["right"])})
    return atlas


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    output_dir = Path("frontend/public/brain")
    write_json(output_dir / "fsaverage5_left.gltf", build_gltf(LEFT_VERTICES))
    write_json(output_dir / "fsaverage5_right.gltf", build_gltf(RIGHT_VERTICES))
    write_json(output_dir / "atlas-desikan-killiany.json", build_atlas())
    write_json(output_dir / "mesh-manifest.json", build_manifest())


if __name__ == "__main__":
    main()
