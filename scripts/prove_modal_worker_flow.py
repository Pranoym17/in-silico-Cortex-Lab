"""Prove Modal -> backend processor -> S3 result -> Redis SSE for one real text run."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.models.experiment import Experiment  # noqa: E402
from app.models.job import Job  # noqa: E402
from app.models.result import Result  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.job_processing import process_modal_inference_job  # noqa: E402
from app.services.result_storage import delete_result_artifact, result_artifact_exists  # noqa: E402
from app.services.sse_broker import get_job_event_broker  # noqa: E402


SPEC_PATH = ROOT / "evidence-inputs" / "short-text.json"


async def run(*, keep: bool) -> dict:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    proof_id = uuid4()
    async with AsyncSessionLocal() as session:
        user = User(supabase_user_id=f"proof-{proof_id}", email=f"proof-{proof_id}@example.invalid")
        session.add(user)
        await session.flush()
        experiment = Experiment(owner_id=user.id, name=f"Modal proof {proof_id}")
        session.add(experiment)
        await session.flush()
        job = Job(experiment_id=experiment.id, owner_id=user.id, run_spec=spec)
        session.add(job)
        await session.commit()
        await session.refresh(job)

        broker = get_job_event_broker()
        processed = await process_modal_inference_job(
            session,
            job.id,
            broker,
            app_name="cortex-lab-tribe-inference",
            function_name="run_real",
            timeout_seconds=900,
            max_attempts=1,
        )
        events = await broker.replay(job.id)
        result = (await session.execute(select(Result).where(Result.job_id == processed.id))).scalar_one_or_none()
        if processed.status.value != "complete" or result is None:
            raise RuntimeError(f"real processor proof failed: {processed.status.value} {processed.error_message or ''}".strip())
        if result.vertex_count != 20_484 or result.timestep_count <= 0:
            raise RuntimeError("stored result does not satisfy the fsaverage5 contract")
        if not result_artifact_exists(result.s3_key):
            raise RuntimeError("stored result artifact is missing from S3")
        event_names = [event.event for event in events]
        required = {"queued", "warming", "progress", "chunk", "complete"}
        if not required.issubset(event_names):
            raise RuntimeError(f"Redis SSE replay is missing events: {sorted(required - set(event_names))}")
        report = {
            "passed": True,
            "job_id": str(job.id),
            "result": {"shape": result.shape, "s3_key": result.s3_key, "metadata": result.metadata_json},
            "redis_events": event_names,
        }
        if not keep:
            delete_result_artifact(result.s3_key)
            await session.delete(job)
            await session.delete(experiment)
            await session.delete(user)
            await session.commit()
        return report


async def main_async(args: argparse.Namespace) -> int:
    try:
        report = await run(keep=args.keep)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="Keep isolated proof records and S3 artifact for inspection")
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
