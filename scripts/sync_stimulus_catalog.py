from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import boto3
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload and verify the licensed stimulus catalog in S3.")
    parser.add_argument("--catalog", type=Path, default=ROOT / "frontend/public/stimuli/v1/catalog.json")
    parser.add_argument("--bucket", default=os.environ.get("S3_BUCKET_NAME"))
    parser.add_argument("--region", default=os.environ.get("AWS_REGION"))
    parser.add_argument("--asset-id", action="append", default=[], help="Upload only one catalog asset ID; repeat as needed.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.bucket:
        parser.error("--bucket or S3_BUCKET_NAME is required")

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    selected_ids = set(args.asset_id)
    assets = [asset for asset in catalog["assets"] if not selected_ids or asset["id"] in selected_ids]
    missing_ids = selected_ids - {asset["id"] for asset in assets}
    if missing_ids:
        parser.error(f"Unknown catalog asset IDs: {', '.join(sorted(missing_ids))}")
    client = boto3.client("s3", region_name=args.region)
    uploaded = 0
    for asset in assets:
        source = ROOT / "frontend/public" / asset["public_path"].removeprefix("/")
        if args.dry_run:
            print(f"DRY RUN {source} -> s3://{args.bucket}/{asset['object_key']}")
            continue
        client.upload_file(
            str(source),
            args.bucket,
            asset["object_key"],
            ExtraArgs={
                "ContentType": asset["mime_type"],
                "Metadata": {
                    "sha256": asset["sha256"],
                    "license": asset["license"],
                    "catalog-version": catalog["catalog_version"],
                },
            },
        )
        head = client.head_object(Bucket=args.bucket, Key=asset["object_key"])
        if head.get("Metadata", {}).get("sha256") != asset["sha256"]:
            raise RuntimeError(f"S3 verification failed for {asset['id']}")
        uploaded += 1
    print(f"{'Validated' if args.dry_run else 'Uploaded and verified'} {len(assets) if args.dry_run else uploaded} assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
