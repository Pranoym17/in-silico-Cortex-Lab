import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "probe_external_services.py"
SPEC = importlib.util.spec_from_file_location("probe_external_services", SCRIPT)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
sys.modules["probe_external_services"] = probe
SPEC.loader.exec_module(probe)


def production_backend():
    return {
        "DEPLOYMENT_STAGE": "production",
        "AWS_REGION": "ca-central-1",
        "PRODUCTION_AWS_REGION": "ca-central-1",
        "PRODUCTION_AWS_ACCOUNT_ID": "123456789012",
        "S3_BUCKET_NAME": "cortex-production",
        "REDIS_URL": "rediss://redis.example.com",
        "SUPABASE_URL": "https://project.supabase.co",
    }


class FakeSession:
    def client(self, service):
        if service == "sts":
            return SimpleNamespace(
                get_caller_identity=lambda: {
                    "Account": "123456789012",
                    "Arn": "arn:aws:iam::123456789012:role/cortex-production",
                }
            )
        return SimpleNamespace(
            get_bucket_location=lambda **kwargs: {"LocationConstraint": "ca-central-1"},
            head_bucket=lambda **kwargs: None,
        )


def test_aws_probe_requires_matching_production_identity_and_region():
    result = probe.probe_aws(production_backend(), session_factory=lambda **kwargs: FakeSession())
    assert result.ready is True
    assert result.evidence["expected_account_matches"] is True


def test_aws_probe_rejects_development_stage():
    backend = production_backend()
    backend["DEPLOYMENT_STAGE"] = "local"
    result = probe.probe_aws(backend, session_factory=lambda **kwargs: FakeSession())
    assert result.ready is False


def test_run_probes_sanitizes_failures():
    def fail(*args, **kwargs):
        raise RuntimeError("secret-bearing provider message")

    results = probe.run_probes({}, {}, aws_probe=fail, redis_probe=fail, supabase_probe=fail)
    assert all(item.ready is False for item in results)
    assert all(item.evidence == {"error_type": "RuntimeError"} for item in results)
    assert all("secret-bearing" not in str(item) for item in results)
