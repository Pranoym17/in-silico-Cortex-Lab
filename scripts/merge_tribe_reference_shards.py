"""Merge ordered, non-overlapping real TRIBE reference shards into one training fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


EXPECTED_VERTICES = 20_484


def load_shard(path: Path) -> tuple[np.ndarray, dict]:
    metadata_path = path.with_suffix(".metadata.json")
    if not metadata_path.is_file():
        raise ValueError(f"Missing metadata sidecar for {path}")
    with np.load(path, allow_pickle=False) as archive:
        matrix = np.asarray(archive["activations"], dtype=np.float32)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    if matrix.ndim != 2 or matrix.shape[1] != EXPECTED_VERTICES:
        raise ValueError(f"{path} is not a [timesteps, {EXPECTED_VERTICES}] reference matrix")
    stimuli = metadata.get("stimuli")
    if not isinstance(stimuli, list):
        raise ValueError(f"{metadata_path} has no stimuli list")
    return matrix, metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shard", type=Path, action="append", required=True, help="NPZ shard path; pass in source-block order.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--deduplicate-blocks",
        action="store_true",
        help="Keep the first complete real output for each block_id and restore chronological order.",
    )
    args = parser.parse_args()

    matrices: list[np.ndarray] = []
    stimuli: list[dict] = []
    deduplicated: list[tuple[int, int, dict, np.ndarray]] = []
    expected_start = 0
    timestep_offset = 0
    for path in args.shard:
        matrix, metadata = load_shard(path)
        source_start = metadata.get("source_block_start")
        source_count = metadata.get("source_block_count")
        shard_stimuli = metadata["stimuli"]
        if not args.deduplicate_blocks and (source_start != expected_start or source_count != len(shard_stimuli)):
            raise ValueError(f"{path} is not the next complete source block range")
        for stimulus in shard_stimuli:
            item = dict(stimulus)
            start = item.get("output_timestep_start")
            count = item.get("output_timestep_count")
            if not isinstance(start, int) or not isinstance(count, int) or count < 1:
                raise ValueError(f"{path} stimulus is missing output_timestep_start")
            if start < 0 or start + count > matrix.shape[0]:
                raise ValueError(f"{path} stimulus timestep range falls outside its activation matrix")
            if args.deduplicate_blocks:
                experiment_start = item.get("experiment_start_ms")
                if not isinstance(experiment_start, int) or not isinstance(item.get("block_id"), str):
                    raise ValueError(f"{path} stimulus is missing block_id or experiment_start_ms")
                deduplicated.append((experiment_start, len(deduplicated), item, matrix[start : start + count]))
                continue
            item["output_timestep_start"] = start + timestep_offset
            stimuli.append(item)
        if not args.deduplicate_blocks:
            matrices.append(matrix)
        expected_start += source_count
        if not args.deduplicate_blocks:
            timestep_offset += matrix.shape[0]

    if args.deduplicate_blocks:
        seen_block_ids: set[str] = set()
        timestep_offset = 0
        for _experiment_start, _arrival_index, item, frames in sorted(deduplicated, key=lambda value: (value[0], value[1])):
            block_id = item["block_id"]
            if block_id in seen_block_ids:
                continue
            seen_block_ids.add(block_id)
            item["output_timestep_start"] = timestep_offset
            item["output_timestep_count"] = int(frames.shape[0])
            stimuli.append(item)
            matrices.append(frames)
            timestep_offset += frames.shape[0]

    merged = np.concatenate(matrices, axis=0)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, activations=merged)
    args.output.with_suffix(".metadata.json").write_text(
        json.dumps({"stimuli": stimuli, "shape": list(merged.shape), "source_shards": [str(path) for path in args.shard]}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Merged {len(args.shard)} shards, {len(stimuli)} blocks, shape {list(merged.shape)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
