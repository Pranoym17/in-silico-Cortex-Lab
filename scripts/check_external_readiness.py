from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDERS = {"", "replace-me", "changeme", "local-dev", "your-value"}
SUPPORTED_AWS_REGIONS = {"ca-central-1", "us-east-1", "us-east-2", "us-west-2"}


@dataclass(frozen=True)
class Check:
    name: str
    ready: bool
    required: bool
    message: str


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip("\"'")
    return values


def configured(value: str | None) -> bool:
    return bool(value and value.strip().lower() not in PLACEHOLDERS)


def valid_url(value: str | None, *, https_required: bool = False) -> bool:
    if not configured(value):
        return False
    parsed = urlparse(value or "")
    return bool(parsed.netloc and parsed.scheme in ({"https"} if https_required else {"http", "https"}))


def build_checks(backend: dict[str, str], frontend: dict[str, str]) -> list[Check]:
    stage = backend.get("DEPLOYMENT_STAGE", backend.get("ENVIRONMENT", "local")).lower()
    production = stage == "production"
    aws_region = backend.get("PRODUCTION_AWS_REGION") if production else backend.get("AWS_REGION")
    supabase_url = backend.get("SUPABASE_URL")
    frontend_supabase_url = frontend.get("NEXT_PUBLIC_SUPABASE_URL")
    usage_mode = backend.get("TRIBE_USAGE_MODE", "")
    gpu_approved = backend.get("MODAL_GPU_TESTS_APPROVED", "false").lower() == "true"
    budget = backend.get("MODAL_GPU_BUDGET_USD", "0")
    try:
        positive_budget = float(budget) > 0
    except ValueError:
        positive_budget = False

    return [
        Check("modal_token_id", configured(backend.get("MODAL_TOKEN_ID")), True, "Modal token ID configured"),
        Check(
            "modal_token_secret",
            configured(backend.get("MODAL_TOKEN_SECRET")),
            True,
            "Modal token secret configured",
        ),
        Check("hf_token", configured(backend.get("HF_TOKEN")), True, "Hugging Face read token configured"),
        Check(
            "gpu_cost_approval",
            gpu_approved and positive_budget,
            True,
            "GPU tests explicitly approved with a positive USD budget",
        ),
        Check(
            "aws_region",
            bool(aws_region in SUPPORTED_AWS_REGIONS),
            True,
            f"AWS region selected ({aws_region or 'missing'})",
        ),
        Check("aws_access_key", configured(backend.get("AWS_ACCESS_KEY_ID")), True, "AWS access key configured"),
        Check("aws_secret_key", configured(backend.get("AWS_SECRET_ACCESS_KEY")), True, "AWS secret key configured"),
        Check("s3_bucket", configured(backend.get("S3_BUCKET_NAME")), True, "S3 bucket configured"),
        Check("redis", configured(backend.get("REDIS_URL")), True, "Redis URL configured"),
        Check("supabase_url", valid_url(supabase_url, https_required=production), True, "Supabase URL configured"),
        Check(
            "supabase_frontend_match",
            configured(frontend_supabase_url) and frontend_supabase_url == supabase_url,
            True,
            "Frontend and backend Supabase URLs match",
        ),
        Check(
            "supabase_anon_key",
            configured(frontend.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")),
            True,
            "Supabase publishable/anon key configured",
        ),
        Check(
            "supabase_jwt",
            configured(backend.get("SUPABASE_JWT_SECRET")),
            True,
            "Supabase JWT verification secret configured",
        ),
        Check(
            "site_url",
            valid_url(frontend.get("NEXT_PUBLIC_SITE_URL"), https_required=production),
            True,
            "Frontend site URL configured",
        ),
        Check(
            "stimulus_license_policy",
            backend.get("STIMULUS_LICENSE_POLICY") == "cc0-public-domain",
            True,
            "Stimulus policy restricts bundled assets to CC0/public domain",
        ),
        Check(
            "tribe_usage_mode",
            usage_mode == "research-noncommercial",
            True,
            "TRIBE usage is explicitly restricted to research/non-commercial use",
        ),
        Check(
            "hf_token_shape",
            bool(re.fullmatch(r"hf_[A-Za-z0-9]{20,}", backend.get("HF_TOKEN", ""))),
            False,
            "Hugging Face token has the expected format",
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Cortex Lab external-service readiness without exposing secrets.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when any required check fails.")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--frontend-env-file", type=Path, default=ROOT / "frontend" / ".env.local")
    args = parser.parse_args()

    backend = {**load_env_file(args.env_file), **os.environ}
    frontend = {**load_env_file(args.frontend_env_file), **os.environ}
    checks = build_checks(backend, frontend)
    required_failures = [check for check in checks if check.required and not check.ready]

    if args.json:
        print(
            json.dumps(
                {
                    "ready": not required_failures,
                    "checks": [asdict(check) for check in checks],
                    "required_failure_count": len(required_failures),
                },
                indent=2,
            )
        )
    else:
        for check in checks:
            marker = "PASS" if check.ready else ("FAIL" if check.required else "WARN")
            print(f"[{marker}] {check.message}")
        print(f"\nExternal readiness: {'READY' if not required_failures else 'BLOCKED'}")
        print(f"Required failures: {len(required_failures)}")

    return 1 if args.strict and required_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
