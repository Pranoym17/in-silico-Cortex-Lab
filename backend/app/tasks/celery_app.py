from typing import Any

from celery import Celery

from app.core.config import get_settings


def create_celery_app(settings: Any) -> Celery:
    """Create an app suitable for Redis locally and SQS in ECS.

    SQS is deliberately configured through an explicit broker URL. Task results
    remain in Redis so SSE and result polling share one low-latency store.
    """
    app = Celery(
        "cortexlab",
        broker=settings.resolved_celery_broker_url,
        backend=settings.resolved_celery_result_backend,
    )
    app.conf.update(
        imports=("app.tasks.inference_task", "app.tasks.optimizer_task"),
        task_default_queue=settings.celery_default_queue,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_track_started=True,
    )
    if settings.resolved_celery_broker_url.startswith("sqs://"):
        if not settings.sqs_queue_url.startswith("https://"):
            raise ValueError("SQS_QUEUE_URL must be an HTTPS AWS queue URL when CELERY_BROKER_URL=sqs://")
        app.conf.broker_transport_options = {
            "region": settings.celery_sqs_region or settings.aws_region,
            "visibility_timeout": settings.celery_sqs_visibility_timeout_seconds,
            "wait_time_seconds": 20,
            "polling_interval": 1,
            "predefined_queues": {
                settings.celery_default_queue: {"url": settings.sqs_queue_url},
            },
        }
    return app


celery_app = create_celery_app(get_settings())

