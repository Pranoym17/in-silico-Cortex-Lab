import json
import runpy
from pathlib import Path

import numpy as np
import pytest


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
capture = runpy.run_path(SCRIPTS / "capture_tribe_reference.py")
merge = runpy.run_path(SCRIPTS / "merge_tribe_reference_shards.py")


def write_shard(path: Path, *, start: int, count: int, timestep_start: int) -> None:
    np.savez_compressed(path, activations=np.ones((2, 20_484), dtype=np.float32))
    path.with_suffix(".metadata.json").write_text(
        json.dumps(
            {
                "source_block_start": start,
                "source_block_count": count,
                "stimuli": [{"output_timestep_start": timestep_start, "output_timestep_count": 2}],
            }
        ),
        encoding="utf-8",
    )


def test_load_shard_requires_real_vertex_width(tmp_path):
    path = tmp_path / "bad.npz"
    np.savez_compressed(path, activations=np.ones((1, 3), dtype=np.float32))
    path.with_suffix(".metadata.json").write_text(json.dumps({"stimuli": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="20484"):
        merge["load_shard"](path)


def test_shard_metadata_contract_is_explicit(tmp_path):
    path = tmp_path / "one.npz"
    write_shard(path, start=0, count=1, timestep_start=0)
    matrix, metadata = merge["load_shard"](path)
    assert matrix.shape == (2, 20_484)
    assert metadata["source_block_start"] == 0
    assert capture["EXPECTED_VERTICES"] == 20_484
