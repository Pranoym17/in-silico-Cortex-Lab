"""Train and export the Cortex Lab eight-class cognitive-state MLP from real TRIBE matrices."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


INPUT_WIDTH = 20_484
LABELS = (
    "Visual - Objects",
    "Visual - Scenes",
    "Face Processing",
    "Language Comprehension",
    "Auditory - Speech",
    "Auditory - Music",
    "Reading",
    "Rest / Low Activation",
)


def collect_training_examples(activations: np.ndarray, metadata: dict, labels: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    stimuli = metadata.get("stimuli")
    if activations.ndim != 2 or activations.shape[1] != INPUT_WIDTH:
        raise ValueError(f"Expected activation matrix [timesteps, {INPUT_WIDTH}].")
    if not isinstance(stimuli, list) or len(stimuli) != len(labels):
        raise ValueError("Stimulus metadata and supplied labels must have matching lengths.")
    examples: list[np.ndarray] = []
    targets: list[int] = []
    groups: list[int] = []
    for group, (stimulus, label) in enumerate(zip(stimuli, labels, strict=True)):
        if label not in LABELS or not isinstance(stimulus, dict):
            raise ValueError("Training labels or stimulus metadata are invalid.")
        start = stimulus.get("output_timestep_start")
        count = stimulus.get("output_timestep_count")
        if not isinstance(start, int) or not isinstance(count, int) or count < 1:
            raise ValueError("Real TRIBE output is missing block timestep mappings.")
        frames = activations[start : start + count]
        if len(frames) != count:
            raise ValueError("TRIBE block timestep mapping falls outside the activation matrix.")
        examples.extend(frames)
        targets.extend([LABELS.index(label)] * count)
        groups.extend([group] * count)
    return np.asarray(examples, dtype=np.float32), np.asarray(targets, dtype=np.int64), np.asarray(groups, dtype=np.int64)


def split_by_block(labels: np.ndarray, groups: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    train_groups: list[int] = []
    validation_groups: list[int] = []
    for label in range(len(LABELS)):
        candidates = sorted(set(groups[labels == label].tolist()))
        if len(candidates) < 2:
            raise ValueError("Each cognitive-state label requires at least two real stimulus blocks for held-out validation.")
        validation_groups.append(candidates[-1])
        train_groups.extend(candidates[:-1])
    return np.isin(groups, train_groups), np.isin(groups, validation_groups)


def train_model(features: np.ndarray, targets: np.ndarray, train_mask: np.ndarray, validation_mask: np.ndarray, *, epochs: int, seed: int):
    import torch

    torch.manual_seed(seed)
    model = torch.nn.Sequential(
        torch.nn.Linear(INPUT_WIDTH, 512),
        torch.nn.ReLU(),
        torch.nn.Linear(512, 256),
        torch.nn.ReLU(),
        torch.nn.Linear(256, 128),
        torch.nn.ReLU(),
        torch.nn.Linear(128, len(LABELS)),
    )
    mean = features[train_mask].mean(axis=0, keepdims=True)
    std = features[train_mask].std(axis=0, keepdims=True)
    std[std < 1e-6] = 1.0
    normalized = (features - mean) / std
    x_train = torch.from_numpy(normalized[train_mask])
    y_train = torch.from_numpy(targets[train_mask])
    x_validation = torch.from_numpy(normalized[validation_mask])
    y_validation = torch.from_numpy(targets[validation_mask])
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = torch.nn.CrossEntropyLoss()
    model.train()
    for _ in range(epochs):
        optimizer.zero_grad()
        loss = loss_fn(model(x_train), y_train)
        loss.backward()
        optimizer.step()
    model.eval()
    with torch.no_grad():
        validation_accuracy = float((model(x_validation).argmax(dim=1) == y_validation).float().mean().item())
        train_accuracy = float((model(x_train).argmax(dim=1) == y_train).float().mean().item())
    return model, mean.astype(np.float32), std.astype(np.float32), train_accuracy, validation_accuracy


def export_artifact(model, output: Path, *, version: str, mean: np.ndarray, std: np.ndarray) -> None:
    layers = [module for module in model.modules() if module.__class__.__name__ == "Linear"]
    values: dict[str, np.ndarray] = {
        "version": np.array(version),
        "labels": np.array(LABELS),
        "mean": mean.reshape(-1).astype(np.float32),
        "std": std.reshape(-1).astype(np.float32),
    }
    for index, layer in enumerate(layers, start=1):
        values[f"w{index}"] = layer.weight.detach().cpu().numpy().T.astype(np.float32)
        values[f"b{index}"] = layer.bias.detach().cpu().numpy().astype(np.float32)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, **values)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metrics-output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260807)
    parser.add_argument("--min-validation-accuracy", type=float, default=0.75)
    args = parser.parse_args()
    activations = np.load(args.matrix)["activations"]
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    label_metadata = json.loads(args.labels.read_text(encoding="utf-8"))
    features, targets, groups = collect_training_examples(activations, metadata, label_metadata["labels"])
    train_mask, validation_mask = split_by_block(targets, groups)
    model, mean, std, train_accuracy, validation_accuracy = train_model(
        features, targets, train_mask, validation_mask, epochs=args.epochs, seed=args.seed
    )
    metrics = {
        "version": "cognitive-states-mlp-v1",
        "architecture": [INPUT_WIDTH, 512, 256, 128, len(LABELS)],
        "training_examples": int(train_mask.sum()),
        "validation_examples": int(validation_mask.sum()),
        "train_accuracy": train_accuracy,
        "validation_accuracy": validation_accuracy,
        "minimum_validation_accuracy": args.min_validation_accuracy,
        "accepted": validation_accuracy >= args.min_validation_accuracy,
        "labels": list(LABELS),
    }
    args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_output.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    if not metrics["accepted"]:
        raise SystemExit("Classifier did not meet the held-out validation threshold; artifact not exported.")
    export_artifact(model, args.output, version=metrics["version"], mean=mean, std=std)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
