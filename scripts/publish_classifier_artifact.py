"""Upload a validated cognitive-classifier artifact to the configured private S3 bucket."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import boto3
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--bucket", default=os.environ.get("S3_BUCKET_NAME"))
    parser.add_argument("--region", default=os.environ.get("AWS_REGION"))
    args = parser.parse_args()
    if not args.artifact.is_file():
        parser.error(f"artifact not found: {args.artifact}")
    if not args.bucket:
        parser.error("--bucket or S3_BUCKET_NAME is required")
    client = boto3.client("s3", region_name=args.region)
    client.upload_file(str(args.artifact), args.bucket, args.key, ExtraArgs={"ContentType": "application/octet-stream"})
    client.head_object(Bucket=args.bucket, Key=args.key)
    print(f"Published s3://{args.bucket}/{args.key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
