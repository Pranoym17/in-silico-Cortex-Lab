import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "generate_classifier_protocol.py"
SPEC = importlib.util.spec_from_file_location("generate_classifier_protocol", SCRIPT_PATH)
assert SPEC is not None
protocol = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["generate_classifier_protocol"] = protocol
SPEC.loader.exec_module(protocol)


def test_protocol_is_balanced_and_within_the_experiment_cap():
    catalog = __import__("json").loads(protocol.CATALOG_PATH.read_text(encoding="utf-8"))
    spec, metadata = protocol.build_protocol(catalog, per_label=2)

    assert len(spec["blocks"]) == 16
    assert len(metadata["labels"]) == 16
    assert {label: metadata["labels"].count(label) for label in protocol.LABELS} == {
        label: 2 for label in protocol.LABELS
    }
    assert max(block["start_ms"] + block["duration_ms"] for block in spec["blocks"]) <= 300_000
