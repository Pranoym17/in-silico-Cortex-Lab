from app.tasks.celery_app import celery_app


def test_celery_registers_inference_and_optimizer_tasks():
    celery_app.loader.import_default_modules()

    assert "run_inference" in celery_app.tasks
    assert "run_optimizer" in celery_app.tasks
