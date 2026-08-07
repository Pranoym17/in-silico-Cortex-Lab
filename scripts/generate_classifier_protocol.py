"""Create a reproducible, balanced real-TRIBE training protocol from licensed stimuli."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "frontend" / "public" / "stimuli" / "v1" / "catalog.json"
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
TEXTS = {
    "Language Comprehension": [
        "The scientist measured a response in the cortical map.",
        "A quiet library contains many carefully arranged books.",
        "The gardener carried water to the flowers at dawn.",
        "A patient reader considered the meaning of each sentence.",
        "The musician listened for changes in the melody.",
        "The researcher compared patterns across repeated trials.",
    ],
    "Auditory - Speech": [
        "A speaker described a familiar walk through the city.",
        "The narrator explained how the experiment would begin.",
        "Please listen to this sentence at a comfortable pace.",
        "The recorded voice described a bright morning sky.",
        "A short spoken story can engage auditory language systems.",
        "The participant heard a clear sequence of everyday words.",
    ],
}


def sha256_text(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def asset_block(asset: dict, label: str, start_ms: int) -> dict:
    return {
        "id": f"{label[:4].lower().replace(' ', '-')}-{start_ms}",
        "type": asset["modality"],
        "condition": label,
        "start_ms": start_ms,
        "duration_ms": int(asset.get("duration_ms") or 4_000),
        "content_hash": f"sha256:{asset['sha256']}",
        "s3_key": asset["object_key"],
        "mime_type": asset["mime_type"],
        **(
            {"display": {"mode": "center"}}
            if asset["modality"] == "image"
            else {"channels": 1, "sample_rate_hz": 16_000, "source_duration_ms": int(asset.get("duration_ms") or 4_000)}
        ),
    }


def text_block(text: str, label: str, start_ms: int) -> dict:
    return {
        "id": f"text-{start_ms}",
        "type": "text",
        "condition": label,
        "start_ms": start_ms,
        "duration_ms": 4_000,
        "content_hash": sha256_text(text),
        "text": text,
        "voice": "tribe_official_gtts",
    }


def select_assets(catalog: dict, category: str, modality: str, count: int, *, required_tag: str | None = None) -> list[dict]:
    assets = [
        item
        for item in catalog["assets"]
        if item["category"] == category and item["modality"] == modality and (required_tag is None or required_tag in item.get("tags", []))
    ]
    if len(assets) < count:
        raise ValueError(f"Catalog needs {count} {modality} assets in category {category}, found {len(assets)}")
    return assets[:count]


def build_protocol(catalog: dict, per_label: int) -> tuple[dict, dict]:
    choices = {
        "Visual - Objects": select_assets(catalog, "objects", "image", per_label),
        "Visual - Scenes": select_assets(catalog, "scenes", "image", per_label),
        "Face Processing": select_assets(catalog, "faces", "image", per_label),
        "Auditory - Music": select_assets(catalog, "audio", "audio", per_label, required_tag="music"),
        "Reading": select_assets(catalog, "words", "image", per_label),
        # TRIBE has no true no-stimulus/rest input. These are explicitly low-information visual baselines.
        "Rest / Low Activation": select_assets(catalog, "patterns", "image", per_label),
    }
    blocks: list[dict] = []
    labels: list[str] = []
    start_ms = 0
    for label in LABELS:
        if label in TEXTS:
            examples = TEXTS[label][:per_label]
            if len(examples) < per_label:
                raise ValueError(f"Need {per_label} text examples for {label}")
            generated = [text_block(text, label, start_ms + index * 4_000) for index, text in enumerate(examples)]
        else:
            generated = []
            for asset in choices[label]:
                generated.append(asset_block(asset, label, start_ms))
                start_ms += generated[-1]["duration_ms"]
            blocks.extend(generated)
            labels.extend([label] * len(generated))
            continue
        blocks.extend(generated)
        labels.extend([label] * len(generated))
        start_ms += len(generated) * 4_000
    return {
        "job_id": "classifier-training-v1",
        "blocks": blocks,
        "settings": {"hrf_offset_ms": 5_000, "target_sample_rate_hz": 2, "surface": "fsaverage5", "atlas": "desikan-killiany"},
    }, {
        "labels": labels,
        "label_order": list(LABELS),
        "per_label": per_label,
        "limitations": [
            "TRIBE predicts average-subject stimulus responses, not measured fMRI.",
            "Rest / Low Activation is a low-information pattern baseline because TRIBE does not accept a no-stimulus resting-state input.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--labels-output", type=Path, required=True)
    parser.add_argument("--per-label", type=int, default=2)
    args = parser.parse_args()
    if args.per_label < 2 or args.per_label > 2:
        parser.error("per-label must be 2 until additional licensed music stimuli are added to the catalog")
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    spec, metadata = build_protocol(catalog, args.per_label)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    args.labels_output.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Wrote {len(spec['blocks'])} labelled blocks to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
