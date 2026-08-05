"""Upload a local media fixture to the configured S3 bucket for live inference proof."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

import boto3
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--key", required=True)
    parser.add_argument("--content-type", required=True)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env", override=True)
    bucket = os.environ.get("S3_BUCKET_NAME")
    region = os.environ.get("AWS_REGION")
    if not bucket or not region:
        parser.error("S3_BUCKET_NAME and AWS_REGION must be configured in the root .env")
    if not args.source.is_file():
        parser.error(f"source does not exist: {args.source}")

    digest = hashlib.sha256(args.source.read_bytes()).hexdigest()
    client = boto3.client("s3", region_name=region)
    client.upload_file(
        str(args.source),
        bucket,
        args.key,
        ExtraArgs={"ContentType": args.content_type, "Metadata": {"sha256": digest, "purpose": "live-proof"}},
    )
    head = client.head_object(Bucket=bucket, Key=args.key)
    if head.get("Metadata", {}).get("sha256") != digest:
        raise RuntimeError("S3 verification failed")
    print(f"Uploaded and verified s3://{bucket}/{args.key}")
    print(f"Content hash: sha256:{digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
