from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray


EXPECTED_LAYER_WIDTHS = (20_484, 512, 256, 128, 8)


class ClassifierArtifactError(ValueError):
    pass


@dataclass(frozen=True)
class CognitiveClassifierArtifact:
    version: str
    labels: tuple[str, ...]
    weights: tuple[NDArray[np.float32], ...]
    biases: tuple[NDArray[np.float32], ...]

    def predict_proba(self, activations: NDArray[np.float32]) -> NDArray[np.float32]:
        if activations.ndim != 2 or activations.shape[1] != self.weights[0].shape[0]:
            raise ClassifierArtifactError(
                f"Classifier requires activation frames shaped [timesteps, {self.weights[0].shape[0]}]."
            )
        values = np.asarray(activations, dtype=np.float32)
        for index, (weight, bias) in enumerate(zip(self.weights, self.biases, strict=True)):
            values = values @ weight + bias
            if index < len(self.weights) - 1:
                values = np.maximum(values, 0.0)
        values = values - np.max(values, axis=1, keepdims=True)
        exp_values = np.exp(values)
        return np.asarray(exp_values / np.sum(exp_values, axis=1, keepdims=True), dtype=np.float32)


def load_cognitive_classifier_artifact(
    path: str | Path,
    *,
    expected_widths: tuple[int, ...] = EXPECTED_LAYER_WIDTHS,
) -> CognitiveClassifierArtifact:
    artifact_path = Path(path)
    if not artifact_path.is_file():
        raise ClassifierArtifactError(f"Cognitive classifier artifact was not found: {artifact_path}")

    try:
        with np.load(artifact_path, allow_pickle=False) as archive:
            version = _required_scalar_string(archive, "version")
            labels = tuple(str(value) for value in archive["labels"].tolist())
            weights = tuple(np.asarray(archive[f"w{index}"], dtype=np.float32) for index in range(1, len(expected_widths)))
            biases = tuple(np.asarray(archive[f"b{index}"], dtype=np.float32) for index in range(1, len(expected_widths)))
    except (KeyError, OSError, ValueError) as exc:
        raise ClassifierArtifactError(f"Cognitive classifier artifact is invalid: {exc}") from exc

    if len(labels) != expected_widths[-1] or len(set(labels)) != len(labels) or any(not label.strip() for label in labels):
        raise ClassifierArtifactError(f"Classifier must define {expected_widths[-1]} unique non-empty labels.")
    for index, (weight, bias, input_width, output_width) in enumerate(
        zip(weights, biases, expected_widths[:-1], expected_widths[1:], strict=True),
        start=1,
    ):
        if weight.shape != (input_width, output_width):
            raise ClassifierArtifactError(f"w{index} must have shape ({input_width}, {output_width}).")
        if bias.shape != (output_width,):
            raise ClassifierArtifactError(f"b{index} must have shape ({output_width},).")
        if not np.isfinite(weight).all() or not np.isfinite(bias).all():
            raise ClassifierArtifactError("Classifier weights and biases must be finite.")
    return CognitiveClassifierArtifact(version=version, labels=labels, weights=weights, biases=biases)


def _required_scalar_string(archive: np.lib.npyio.NpzFile, key: str) -> str:
    value = archive[key]
    if value.size != 1:
        raise ClassifierArtifactError(f"{key} must contain exactly one value.")
    text = str(value.item()).strip()
    if not text:
        raise ClassifierArtifactError(f"{key} must be non-empty.")
    return text
