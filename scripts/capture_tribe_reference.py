"""Save a real TRIBE Modal stream as a private compressed reference matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


EXPECTED_VERTICES = 20_484


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--app", default="cortex-lab-tribe-inference")
    parser.add_argument("--function", default="run_real")
    parser.add_argument("--max-blocks", type=int, default=0, help="Capture only the first N blocks for bounded shard runs.")
    args = parser.parse_args()

    import modal

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    if args.max_blocks:
        blocks = spec.get("blocks")
        if not isinstance(blocks, list) or args.max_blocks < 1:
            parser.error("--max-blocks requires a positive block count in the input spec")
        spec["blocks"] = blocks[: args.max_blocks]
    chunks: list[tuple[int, np.ndarray]] = []
    metadata: list[dict] = []
    completed = False
    function = modal.Function.from_name(args.app, args.function)
    for event in function.remote_gen(spec):
        if event.get("type") == "stimulus_metadata":
            metadata.append({key: value for key, value in event.items() if key != "activations"})
        elif event.get("type") == "chunk":
            shape = event.get("shape")
            if not isinstance(shape, list) or len(shape) != 2 or shape[1] != EXPECTED_VERTICES:
                raise ValueError("TRIBE chunk does not match the fsaverage5 vertex contract")
            matrix = np.frombuffer(event["activations"], dtype="<f4").reshape(shape).copy()
            chunks.append((int(event["timestep_start"]), matrix))
        elif event.get("type") == "complete":
            completed = True

    if not completed or not chunks:
        raise RuntimeError("TRIBE reference run did not complete with activation chunks")
    chunks.sort(key=lambda item: item[0])
    activations = np.concatenate([matrix for _, matrix in chunks], axis=0)
    if activations.shape[1] != EXPECTED_VERTICES:
        raise ValueError("reference matrix does not match fsaverage5")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, activations=activations)
    args.output.with_suffix(".metadata.json").write_text(
        json.dumps({"spec": spec, "stimuli": metadata, "shape": list(activations.shape)}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Reference fixture: {args.output}")
    print(f"Shape: {list(activations.shape)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
