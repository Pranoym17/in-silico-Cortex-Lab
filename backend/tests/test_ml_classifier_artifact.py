import numpy as np
import pytest

from app.services.ml_classifier_artifact import ClassifierArtifactError, load_cognitive_classifier_artifact


def write_artifact(path, *, widths=(4, 3, 2), labels=("rest", "active")):
    values = {
        "version": np.array("test-v1"),
        "labels": np.array(labels),
    }
    for index, (input_width, output_width) in enumerate(zip(widths, widths[1:]), start=1):
        values[f"w{index}"] = np.full((input_width, output_width), 0.1, dtype=np.float32)
        values[f"b{index}"] = np.zeros(output_width, dtype=np.float32)
    np.savez(path, **values)


def test_load_classifier_artifact_validates_and_predicts(tmp_path):
    path = tmp_path / "classifier.npz"
    write_artifact(path)

    classifier = load_cognitive_classifier_artifact(path, expected_widths=(4, 3, 2))
    probabilities = classifier.predict_proba(np.ones((2, 4), dtype=np.float32))

    assert classifier.version == "test-v1"
    assert probabilities.shape == (2, 2)
    assert np.allclose(np.sum(probabilities, axis=1), 1.0)


def test_load_classifier_artifact_rejects_wrong_weight_shape(tmp_path):
    path = tmp_path / "classifier.npz"
    write_artifact(path)

    with pytest.raises(ClassifierArtifactError, match="w1 must have shape"):
        load_cognitive_classifier_artifact(path, expected_widths=(5, 3, 2))
