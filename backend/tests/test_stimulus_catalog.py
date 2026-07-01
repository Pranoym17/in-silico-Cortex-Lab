import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "frontend" / "public" / "stimuli" / "v1" / "catalog.json"


def test_catalog_files_hashes_and_licenses_are_complete():
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    assert catalog["asset_count"] == 204
    assert len(catalog["assets"]) == 204
    assert catalog["license_policy"] == "cc0-public-domain"
    assert len({asset["id"] for asset in catalog["assets"]}) == 204

    for asset in catalog["assets"]:
        path = ROOT / "frontend" / "public" / asset["public_path"].removeprefix("/")
        assert path.is_file(), asset["id"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == asset["sha256"]
        assert asset["license"] == "CC0-1.0"
        assert asset["redistribution_permitted"] is True
        assert asset["object_key"].startswith("stimulus-library/v1/")
