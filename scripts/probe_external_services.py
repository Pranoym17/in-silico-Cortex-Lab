from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import boto3
import redis

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from check_external_readiness import ROOT, configured, load_env_file  # noqa: E402


@dataclass(frozen=True)
class Probe:
    name: str
    ready: bool
    message: str
    evidence: dict[str, str | bool]


def probe_aws(
    values: dict[str, str],
    *,
    session_factory: Any = boto3.Session,
) -> Probe:
    region = values.get("AWS_REGION", "")
    bucket = values.get("S3_BUCKET_NAME", "")
    expected_account = values.get("PRODUCTION_AWS_ACCOUNT_ID", "")
    session = session_factory(
        region_name=region,
        aws_access_key_id=values.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=values.get("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=values.get("AWS_SESSION_TOKEN"),
    )
    identity = session.client("sts").get_caller_identity()
    s3 = session.client("s3")
    bucket_region = s3.get_bucket_location(Bucket=bucket).get("LocationConstraint") or "us-east-1"
    s3.head_bucket(Bucket=bucket)
    account = str(identity["Account"])
    production = values.get("DEPLOYMENT_STAGE", "local").lower() == "production"
    ready = (
        configured(expected_account)
        and account == expected_account
        and production
        and bucket_region == values.get("PRODUCTION_AWS_REGION")
    )
    return Probe(
        name="aws",
        ready=ready,
        message="AWS identity, bucket access, and production region verified",
        evidence={
            "account": account,
            "principal_arn": str(identity["Arn"]),
            "bucket": bucket,
            "bucket_region": bucket_region,
            "deployment_stage": values.get("DEPLOYMENT_STAGE", "local"),
            "expected_account_matches": account == expected_account,
        },
    )


def probe_redis(values: dict[str, str], *, client_factory: Any = redis.from_url) -> Probe:
    client = client_factory(values["REDIS_URL"], socket_connect_timeout=8, socket_timeout=8)
    ready = bool(client.ping())
    return Probe("redis", ready, "Redis PING succeeded", {"ping": ready})


def probe_supabase(
    backend: dict[str, str],
    frontend: dict[str, str],
    *,
    opener: Any = urlopen,
) -> Probe:
    base = backend["SUPABASE_URL"].rstrip("/")
    key = frontend.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")
    request = Request(f"{base}/auth/v1/.well-known/jwks.json", headers={"apikey": key})
    with opener(request, timeout=15) as response:
        content_type = response.headers.get_content_type()
        ready = response.status == 200 and content_type == "application/json"
        return Probe(
            "supabase",
            ready,
            "Supabase authentication JWKS endpoint is reachable",
            {"status": str(response.status), "content_type": content_type, "project_url": base},
        )


def run_probes(
    backend: dict[str, str],
    frontend: dict[str, str],
    *,
    aws_probe: Any = probe_aws,
    redis_probe: Any = probe_redis,
    supabase_probe: Any = probe_supabase,
) -> list[Probe]:
    probes: list[Probe] = []
    for name, operation in (
        ("aws", lambda: aws_probe(backend)),
        ("redis", lambda: redis_probe(backend)),
        ("supabase", lambda: supabase_probe(backend, frontend)),
    ):
        try:
            probes.append(operation())
        except Exception as error:
            probes.append(Probe(name, False, f"{name.upper()} probe failed", {"error_type": type(error).__name__}))
    return probes


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe configured cloud services without printing secret values.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--frontend-env-file", type=Path, default=ROOT / "frontend" / ".env.local")
    args = parser.parse_args()
    backend = {**load_env_file(args.env_file), **os.environ}
    frontend = {**load_env_file(args.frontend_env_file), **os.environ}
    probes = run_probes(backend, frontend)
    failures = [probe for probe in probes if not probe.ready]

    if args.json:
        print(json.dumps({"ready": not failures, "probes": [asdict(probe) for probe in probes]}, indent=2))
    else:
        for probe in probes:
            print(f"[{'PASS' if probe.ready else 'FAIL'}] {probe.message}")
            for key, value in probe.evidence.items():
                print(f"  {key}: {value}")
        print(f"\nLive external services: {'READY' if not failures else 'BLOCKED'}")

    return 1 if args.strict and failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
