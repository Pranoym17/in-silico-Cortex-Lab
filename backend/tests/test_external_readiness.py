import importlib.util
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_external_readiness.py"
SPEC = importlib.util.spec_from_file_location("check_external_readiness", SCRIPT)
assert SPEC and SPEC.loader
readiness = importlib.util.module_from_spec(SPEC)
sys.modules["check_external_readiness"] = readiness
SPEC.loader.exec_module(readiness)


def valid_backend():
    return {
        "DEPLOYMENT_STAGE": "production",
        "MODAL_TOKEN_ID": "ak-test",
        "MODAL_TOKEN_SECRET": "as-test",
        "HF_TOKEN": "hf_abcdefghijklmnopqrstuvwxyz",
        "MODAL_GPU_TESTS_APPROVED": "true",
        "MODAL_GPU_BUDGET_USD": "25",
        "PRODUCTION_AWS_REGION": "ca-central-1",
        "AWS_ACCESS_KEY_ID": "AKIA_TEST",
        "AWS_SECRET_ACCESS_KEY": "secret",
        "S3_BUCKET_NAME": "cortex-production",
        "REDIS_URL": "rediss://redis.example.com:6379",
        "SUPABASE_URL": "https://project.supabase.co",
        "SUPABASE_JWT_SECRET": "jwt-secret",
        "STIMULUS_LICENSE_POLICY": "cc0-public-domain",
        "TRIBE_USAGE_MODE": "research-noncommercial",
    }


def valid_frontend():
    return {
        "NEXT_PUBLIC_SUPABASE_URL": "https://project.supabase.co",
        "NEXT_PUBLIC_SUPABASE_ANON_KEY": "publishable-key",
        "NEXT_PUBLIC_SITE_URL": "https://cortex.example.com",
    }


def test_complete_external_configuration_is_ready():
    checks = readiness.build_checks(valid_backend(), valid_frontend())
    assert all(check.ready for check in checks if check.required)


def test_paid_tribe_mode_and_unapproved_gpu_are_blocked():
    backend = valid_backend()
    backend["TRIBE_USAGE_MODE"] = "commercial"
    backend["MODAL_GPU_TESTS_APPROVED"] = "false"
    checks = {check.name: check for check in readiness.build_checks(backend, valid_frontend())}
    assert checks["tribe_usage_mode"].ready is False
    assert checks["gpu_cost_approval"].ready is False


def test_production_requires_https_and_matching_supabase_projects():
    frontend = valid_frontend()
    frontend["NEXT_PUBLIC_SITE_URL"] = "http://cortex.example.com"
    frontend["NEXT_PUBLIC_SUPABASE_URL"] = "https://other.supabase.co"
    checks = {check.name: check for check in readiness.build_checks(valid_backend(), frontend)}
    assert checks["site_url"].ready is False
    assert checks["supabase_frontend_match"].ready is False
