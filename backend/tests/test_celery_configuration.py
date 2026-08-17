from types import SimpleNamespace

import pytest

from app.tasks.celery_app import create_celery_app


def settings(**overrides):
    values = {
        "resolved_celery_broker_url": "redis://localhost:6379/0",
        "resolved_celery_result_backend": "redis://localhost:6379/0",
        "celery_default_queue": "cortexlab",
        "sqs_queue_url": "http://localhost:4566/000000000000/cortexlab-jobs",
        "celery_sqs_region": None,
        "aws_region": "us-east-2",
        "celery_sqs_visibility_timeout_seconds": 1800,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_redis_is_the_local_default_broker_and_result_backend():
    app = create_celery_app(settings())

    assert app.conf.broker_url == "redis://localhost:6379/0"
    assert app.conf.result_backend == "redis://localhost:6379/0"
    assert app.conf.task_acks_late is True
    assert app.conf.worker_prefetch_multiplier == 1


def test_sqs_uses_predefined_queue_and_redis_results():
    app = create_celery_app(
        settings(
            resolved_celery_broker_url="sqs://",
            resolved_celery_result_backend="rediss://cache.example:6379/0",
            sqs_queue_url="https://sqs.us-east-2.amazonaws.com/123456789012/cortexlab-staging",
        )
    )

    assert app.conf.broker_transport_options["region"] == "us-east-2"
    assert app.conf.broker_transport_options["predefined_queues"]["cortexlab"]["url"].endswith("cortexlab-staging")
    assert app.conf.result_backend == "rediss://cache.example:6379/0"


def test_sqs_requires_a_real_https_queue_url():
    with pytest.raises(ValueError, match="SQS_QUEUE_URL"):
        create_celery_app(settings(resolved_celery_broker_url="sqs://"))
