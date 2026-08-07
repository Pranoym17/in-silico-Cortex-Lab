from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("cortexlab", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.imports = ("app.tasks.inference_task", "app.tasks.optimizer_task")

