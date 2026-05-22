from types import SimpleNamespace
from uuid import uuid4

from fastapi import BackgroundTasks

from app.services.job_dispatch import dispatch_inference_job, process_job_in_background


def test_dispatch_inference_job_adds_background_task(monkeypatch):
    job_id = uuid4()
    background_tasks = BackgroundTasks()

    monkeypatch.setattr("app.services.job_dispatch.get_settings", lambda: SimpleNamespace(job_execution_mode="background"))

    dispatch_inference_job(background_tasks, job_id)

    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].func is process_job_in_background
    assert background_tasks.tasks[0].args == (job_id,)


def test_dispatch_inference_job_can_leave_jobs_manual(monkeypatch):
    background_tasks = BackgroundTasks()

    monkeypatch.setattr("app.services.job_dispatch.get_settings", lambda: SimpleNamespace(job_execution_mode="manual"))

    dispatch_inference_job(background_tasks, uuid4())

    assert background_tasks.tasks == []
