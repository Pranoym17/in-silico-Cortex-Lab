import runpy
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "sync_stimulus_catalog.py"


def test_sync_script_loads_canonical_root_environment():
    namespace = runpy.run_path(SCRIPT)

    assert namespace["ROOT"].name == "in-silico-Cortex-Lab"
    assert namespace["load_dotenv"]
