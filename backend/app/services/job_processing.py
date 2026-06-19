from datetime import UTC, datetime
import logging
import time
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus
from app.schemas.run import RunExperimentRequest
from app.schemas.sse import CompleteEvent, ErrorEvent, ProgressEvent, QueuedEvent, WarmingEvent
from app.services.activation_events import fake_activation_chunk
from app.services.error_codes import JobErrorCode, is_retryable_job_error, normalize_job_error_code
from app.services.modal_inference import ModalInferenceError, encode_modal_chunk_event, stream_deployed_modal_events
from app.services.result_cache import CachedResult, cached_result_to_metadata, set_cached_result, text_result_cache_context
from app.services.result_storage import ActivationMatrixAssembler, ResultStorageError, store_job_result
from app.services.sse_broker import JobEventBroker, get_job_event_broker

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {JobStatus.complete, JobStatus.failed, JobStatus.cancelled}
FAKE_VERTEX_COUNT = 16
FAKE_TIMESTEPS_PER_BLOCK = 1
MAX_USER_ERROR_MESSAGE_LENGTH = 600


class JobProcessingError(RuntimeError):
    pass


def classify_inference_exception(exc: Exception, *, chunk_seen: bool) -> JobErrorCode:
    if isinstance(exc, ResultStorageError):
        return "result_storage_failed"

    message = str(exc).lower()
    if "timeout" in message or "timed out" in message or "deadline" in message:
        return "timeout"
    if "out of memory" in message or "oom" in message or "cuda memory" in message:
        return "modal_oom"
    if "model_access_required" in message:
        return "model_access_required"
    if "tribe_access_denied" in message:
        return "tribe_access_denied"
    if chunk_seen:
        return "partial_failure"
    return "internal_error"


def user_facing_inference_failure(exc: Exception, *, chunk_seen: bool) -> str:
    classified = classify_inference_exception(exc, chunk_seen=chunk_seen)
    if classified == "timeout":
        return "Inference timed out before completing."
    if classified == "modal_oom":
        return "Modal ran out of memory while running inference."
    if classified == "result_storage_failed":
        return "Inference finished, but the result artifact could not be saved."

    if chunk_seen:
        return "Inference failed after streaming partial results."

    message = str(exc).strip()
    if not message:
        return "Inference failed."

    if message.startswith("Modal inference call failed: "):
        message = message.removeprefix("Modal inference call failed: ").strip()

    if "Modal provider selected, but the modal package is not installed" in message:
        return message

    if "Function not found" in message or "App not found" in message:
        return f"Modal inference endpoint was not found. Check MODAL_APP_NAME and MODAL_FUNCTION_NAME. Details: {message}"

    if "TRIBE predicted" in message and "TRIBE_EXPECTED_VERTEX_COUNT" in message:
        return message

    if "model_access_required" in message or "tribe_access_denied" in message:
        return message

    if len(message) > MAX_USER_ERROR_MESSAGE_LENGTH:
        message = f"{message[:MAX_USER_ERROR_MESSAGE_LENGTH].rstrip()}..."
    return message


async def get_job_for_processing(session: AsyncSession, job_id: UUID) -> Job:
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise JobProcessingError(f"Job {job_id} was not found")
    return job


async def mark_job_failed(
    session: AsyncSession,
    job: Job,
    *,
    error_code: str,
    error_message: str,
) -> Job:
    job.status = JobStatus.failed
    job.error_code = error_code
    job.error_message = error_message[:4000]
    job.completed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(job)
    return job


async def job_was_cancelled(session: AsyncSession, job: Job) -> bool:
    await session.refresh(job)
    return job.status == JobStatus.cancelled


async def rollback_if_cancelled_before_completion(session: AsyncSession, job: Job) -> bool:
    if await job_was_cancelled(session, job):
        await session.rollback()
        await session.refresh(job)
        return True
    return False


async def publish_job_error(
    broker: JobEventBroker,
    job: Job,
    *,
    code: str | None,
    message: str,
    retryable: bool | None = None,
    last_timestep: int | None = None,
) -> None:
    normalized_code = normalize_job_error_code(code)
    await broker.publish(
        job.id,
        "error",
        ErrorEvent(
            job_id=str(job.id),
            code=normalized_code,
            message=message,
            retryable=is_retryable_job_error(normalized_code) if retryable is None else retryable,
            last_timestep=last_timestep,
        ).model_dump(mode="json"),
    )


async def create_result_row_from_cache(session: AsyncSession, job: Job, cached: CachedResult):
    from app.models.result import Result

    result = Result(
        job_id=job.id,
        experiment_id=job.experiment_id,
        owner_id=job.owner_id,
        s3_key=cached.s3_key,
        format=cached.format,
        dtype=cached.dtype,
        shape=cached.shape,
        vertex_count=cached.vertex_count,
        timestep_count=cached.timestep_count,
        sample_rate_hz=cached.sample_rate_hz,
        model_name=cached.model_name,
        model_version=cached.model_version,
        metadata_json=cached_result_to_metadata(cached),
    )
    session.add(result)
    await session.flush()
    return result


async def complete_job_from_cached_result(
    session: AsyncSession,
    job_id: UUID,
    cached: CachedResult,
    broker: JobEventBroker | None = None,
) -> Job:
    broker = broker or get_job_event_broker()
    job = await get_job_for_processing(session, job_id)

    if job.status in TERMINAL_STATUSES:
        return job

    logger.info("job_started", extra={"job_id": str(job.id), "experiment_id": str(job.experiment_id), "user_id": str(job.owner_id), "provider": "fake"})
    await broker.publish(
        job.id,
        "queued",
        QueuedEvent(job_id=str(job.id), status=JobStatus.queued).model_dump(mode="json"),
    )
    await broker.publish(
        job.id,
        "progress",
        ProgressEvent(
            job_id=str(job.id),
            completed_blocks=1,
            total_blocks=1,
            completed_timesteps=cached.timestep_count,
        ).model_dump(mode="json"),
    )
    result = await create_result_row_from_cache(session, job, cached)
    job.status = JobStatus.complete
    job.completed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(job)
    await broker.publish(
        job.id,
        "complete",
        CompleteEvent(
            job_id=str(job.id),
            status=JobStatus.complete,
            result_s3_key=result.s3_key,
            timesteps=cached.timestep_count,
            vertex_count=cached.vertex_count,
        ).model_dump(mode="json"),
    )
    return job


async def process_fake_inference_job(
    session: AsyncSession,
    job_id: UUID,
    broker: JobEventBroker | None = None,
) -> Job:
    broker = broker or get_job_event_broker()
    job = await get_job_for_processing(session, job_id)

    if job.status in TERMINAL_STATUSES:
        return job

    logger.info("job_started", extra={"job_id": str(job.id), "experiment_id": str(job.experiment_id), "user_id": str(job.owner_id), "provider": "fake"})
    await broker.publish(
        job.id,
        "queued",
        QueuedEvent(job_id=str(job.id), status=JobStatus.queued).model_dump(mode="json"),
    )

    try:
        run_request = RunExperimentRequest.model_validate(job.run_spec)
    except ValidationError as exc:
        logger.info("job_validation_failed", extra={"job_id": str(job.id), "experiment_id": str(job.experiment_id), "user_id": str(job.owner_id), "provider": "fake", "error_code": "validation_failed"})
        failed_job = await mark_job_failed(
            session,
            job,
            error_code="validation_failed",
            error_message=str(exc),
        )
        await broker.publish(
            job.id,
            "error",
            ErrorEvent(
                job_id=str(job.id),
                code="validation_failed",
                message="Run specification failed validation.",
                retryable=False,
            ).model_dump(mode="json"),
        )
        return failed_job
    logger.info("job_validation_passed", extra={"job_id": str(job.id), "experiment_id": str(job.experiment_id), "user_id": str(job.owner_id), "provider": "modal"})
    logger.info("job_validation_passed", extra={"job_id": str(job.id), "experiment_id": str(job.experiment_id), "user_id": str(job.owner_id), "provider": "fake"})

    job.status = JobStatus.warming
    await session.commit()
    await session.refresh(job)
    await broker.publish(
        job.id,
        "warming",
        WarmingEvent(job_id=str(job.id), estimated_seconds=1).model_dump(mode="json"),
    )

    started_at = datetime.now(UTC)
    job.status = JobStatus.running
    job.started_at = job.started_at or started_at
    job.error_code = None
    job.error_message = None
    await session.commit()
    await session.refresh(job)

    total_blocks = len(run_request.blocks)
    completed_timesteps = 0
    await broker.publish(
        job.id,
        "progress",
        ProgressEvent(
            job_id=str(job.id),
            completed_blocks=0,
            total_blocks=total_blocks,
            completed_timesteps=completed_timesteps,
        ).model_dump(mode="json"),
    )

    sample_rate_hz = run_request.settings.target_sample_rate_hz
    result_assembler = ActivationMatrixAssembler()
    for chunk_index, block in enumerate(run_request.blocks):
        if await job_was_cancelled(session, job):
            logger.info("job_cancelled_observed", extra={"job_id": str(job.id), "experiment_id": str(job.experiment_id), "user_id": str(job.owner_id), "provider": "fake"})
            return job
        chunk = fake_activation_chunk(
            job_id=str(job.id),
            block_id=block.id,
            chunk_index=chunk_index,
            timestep_start=completed_timesteps,
            timestep_count=FAKE_TIMESTEPS_PER_BLOCK,
            vertex_count=FAKE_VERTEX_COUNT,
            sample_rate_hz=sample_rate_hz,
        )
        result_assembler.add_chunk(decode_chunk_envelope(chunk.payload))
        await broker.publish(job.id, "chunk", chunk.model_dump(mode="json"))

        completed_timesteps += FAKE_TIMESTEPS_PER_BLOCK
        await broker.publish(
            job.id,
            "progress",
            ProgressEvent(
                job_id=str(job.id),
                completed_blocks=chunk_index + 1,
                total_blocks=total_blocks,
                completed_timesteps=completed_timesteps,
            ).model_dump(mode="json"),
        )

    try:
        if await job_was_cancelled(session, job):
            return job
        result = await store_job_result(
            session,
            job,
            result_assembler.assemble(),
            sample_rate_hz=result_assembler.sample_rate_hz,
            model_name="fake",
            model_version="dev",
            metadata={
                "provider": "fake",
                "surface": run_request.settings.surface,
                "atlas": run_request.settings.atlas,
            },
        )
    except Exception as exc:
        code = classify_inference_exception(exc, chunk_seen=True)
        logger.exception("job_result_storage_failed", extra={"job_id": str(job.id), "experiment_id": str(job.experiment_id), "user_id": str(job.owner_id), "provider": "fake", "error_code": code})
        failed_job = await mark_job_failed(session, job, error_code=code, error_message=str(exc))
        await publish_job_error(
            broker,
            job,
            code=code,
            message=user_facing_inference_failure(exc, chunk_seen=True),
            last_timestep=completed_timesteps - 1 if completed_timesteps > 0 else None,
        )
        return failed_job
    if await rollback_if_cancelled_before_completion(session, job):
        return job
    if len(run_request.blocks) == 1 and run_request.blocks[0].type == "text":
        set_cached_result(
            run_request.blocks[0].content_hash,
            result,
            text_result_cache_context(run_request.blocks[0], run_request.settings, model_name="fake", model_version="dev"),
        )
    job.status = JobStatus.complete
    job.completed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(job)
    await broker.publish(
        job.id,
        "complete",
        CompleteEvent(
            job_id=str(job.id),
            status=JobStatus.complete,
            result_s3_key=result.s3_key,
            timesteps=completed_timesteps,
            vertex_count=FAKE_VERTEX_COUNT,
        ).model_dump(mode="json"),
    )
    logger.info("job_completed", extra={"job_id": str(job.id), "experiment_id": str(job.experiment_id), "user_id": str(job.owner_id), "provider": "fake", "duration_ms": int((datetime.now(UTC) - started_at).total_seconds() * 1000)})
    return job


async def process_modal_inference_job(
    session: AsyncSession,
    job_id: UUID,
    broker: JobEventBroker | None = None,
    *,
    app_name: str,
    function_name: str,
    environment_name: str | None = None,
    timeout_seconds: int | None = None,
    max_attempts: int = 1,
) -> Job:
    broker = broker or get_job_event_broker()
    job = await get_job_for_processing(session, job_id)

    if job.status in TERMINAL_STATUSES:
        return job

    started_monotonic = time.monotonic()

    await broker.publish(
        job.id,
        "queued",
        QueuedEvent(job_id=str(job.id), status=JobStatus.queued).model_dump(mode="json"),
    )

    try:
        run_request = RunExperimentRequest.model_validate(job.run_spec)
    except ValidationError as exc:
        failed_job = await mark_job_failed(
            session,
            job,
            error_code="validation_failed",
            error_message=str(exc),
        )
        await broker.publish(
            job.id,
            "error",
            ErrorEvent(
                job_id=str(job.id),
                code="validation_failed",
                message="Run specification failed validation.",
                retryable=False,
            ).model_dump(mode="json"),
        )
        return failed_job

    modal_spec = run_request.model_dump(mode="json")
    modal_spec["job_id"] = str(job.id)

    chunk_seen = False
    completed_timesteps = 0
    vertex_count = 0
    result_assembler = ActivationMatrixAssembler()

    try:
        logger.info("modal_call_started", extra={"job_id": str(job.id), "experiment_id": str(job.experiment_id), "user_id": str(job.owner_id), "provider": "modal", "attempt": 1})
        async for event in stream_deployed_modal_events(
            app_name=app_name,
            function_name=function_name,
            environment_name=environment_name,
            spec=modal_spec,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
        ):
            event_type = event.get("type")
            if await job_was_cancelled(session, job):
                logger.info("job_cancelled_observed", extra={"job_id": str(job.id), "experiment_id": str(job.experiment_id), "user_id": str(job.owner_id), "provider": "modal"})
                return job

            if event_type == "warming":
                job.status = JobStatus.warming
                await session.commit()
                await session.refresh(job)
                await broker.publish(
                    job.id,
                    "warming",
                    WarmingEvent(
                        job_id=str(job.id),
                        reason=str(event.get("reason") or "modal_cold_start"),
                        estimated_seconds=int(event.get("estimated_seconds") or 0),
                    ).model_dump(mode="json"),
                )
                continue

            if event_type == "progress":
                if job.status in {JobStatus.queued, JobStatus.warming}:
                    job.status = JobStatus.running
                    job.started_at = job.started_at or datetime.now(UTC)
                    await session.commit()
                    await session.refresh(job)

                completed_timesteps = int(event.get("completed_timesteps") or completed_timesteps)
                await broker.publish(
                    job.id,
                    "progress",
                    ProgressEvent(
                        job_id=str(job.id),
                        completed_blocks=int(event.get("completed_blocks") or 0),
                        total_blocks=int(event.get("total_blocks") or len(run_request.blocks)),
                        completed_timesteps=completed_timesteps,
                    ).model_dump(mode="json"),
                )
                continue

            if event_type == "chunk":
                if job.status != JobStatus.streaming:
                    job.status = JobStatus.streaming
                    job.started_at = job.started_at or datetime.now(UTC)
                    await session.commit()
                    await session.refresh(job)

                envelope = encode_modal_chunk_event(event)
                result_assembler.add_chunk(event)
                chunk_seen = True
                completed_timesteps = max(
                    completed_timesteps,
                    int(event["timestep_start"]) + int(event["timestep_count"]),
                )
                vertex_count = int(event["vertex_count"])
                await broker.publish(job.id, "chunk", envelope.model_dump(mode="json"))
                continue

            if event_type == "complete":
                if await job_was_cancelled(session, job):
                    return job
                completed_timesteps = int(event.get("timesteps") or completed_timesteps)
                vertex_count = int(event.get("vertex_count") or vertex_count)
                result = await store_job_result(
                    session,
                    job,
                    result_assembler.assemble(),
                    sample_rate_hz=result_assembler.sample_rate_hz,
                    model_name="tribev2",
                    model_version=str(event.get("model_version")) if event.get("model_version") else None,
                    metadata={
                        "provider": "modal",
                        "app_name": app_name,
                        "function_name": function_name,
                        "surface": run_request.settings.surface,
                        "atlas": run_request.settings.atlas,
                    },
                )
                if await rollback_if_cancelled_before_completion(session, job):
                    return job
                if len(run_request.blocks) == 1 and run_request.blocks[0].type == "text":
                    set_cached_result(
                        run_request.blocks[0].content_hash,
                        result,
                        text_result_cache_context(
                            run_request.blocks[0],
                            run_request.settings,
                            model_name="tribev2",
                        ),
                    )
                job.status = JobStatus.complete
                job.completed_at = datetime.now(UTC)
                await session.commit()
                await session.refresh(job)
                await broker.publish(
                    job.id,
                    "complete",
                    CompleteEvent(
                        job_id=str(job.id),
                        status=JobStatus.complete,
                        result_s3_key=result.s3_key,
                        timesteps=completed_timesteps,
                        vertex_count=vertex_count,
                    ).model_dump(mode="json"),
                )
                logger.info("modal_call_completed", extra={"job_id": str(job.id), "experiment_id": str(job.experiment_id), "user_id": str(job.owner_id), "provider": "modal", "duration_ms": int((time.monotonic() - started_monotonic) * 1000)})
                logger.info("job_completed", extra={"job_id": str(job.id), "experiment_id": str(job.experiment_id), "user_id": str(job.owner_id), "provider": "modal", "duration_ms": int((time.monotonic() - started_monotonic) * 1000)})
                return job

            if event_type == "error":
                code = normalize_job_error_code(str(event.get("code") or "internal_error"))
                message = str(event.get("message") or "Modal inference failed.")
                logger.info("modal_call_failed", extra={"job_id": str(job.id), "experiment_id": str(job.experiment_id), "user_id": str(job.owner_id), "provider": "modal", "error_code": code, "duration_ms": int((time.monotonic() - started_monotonic) * 1000)})
                failed_job = await mark_job_failed(
                    session,
                    job,
                    error_code=code,
                    error_message=message,
                )
                await publish_job_error(
                    broker,
                    job,
                    code=code,
                    message=message,
                    retryable=bool(event.get("retryable", is_retryable_job_error(code))),
                    last_timestep=event.get("last_timestep"),
                )
                logger.info("sse_error_emitted", extra={"job_id": str(job.id), "experiment_id": str(job.experiment_id), "user_id": str(job.owner_id), "provider": "modal", "error_code": code})
                return failed_job

            raise ModalInferenceError(f"Unsupported Modal event type: {event_type}")
    except Exception as exc:
        code = classify_inference_exception(exc, chunk_seen=chunk_seen)
        message = str(exc)
        logger.exception("modal_call_failed", extra={"job_id": str(job.id), "experiment_id": str(job.experiment_id), "user_id": str(job.owner_id), "provider": "modal", "error_code": code, "duration_ms": int((time.monotonic() - started_monotonic) * 1000)})
        failed_job = await mark_job_failed(session, job, error_code=code, error_message=message)
        user_message = user_facing_inference_failure(exc, chunk_seen=chunk_seen)
        await publish_job_error(
            broker,
            job,
            code=code,
            message=user_message,
            last_timestep=completed_timesteps - 1 if completed_timesteps > 0 else None,
        )
        logger.info("sse_error_emitted", extra={"job_id": str(job.id), "experiment_id": str(job.experiment_id), "user_id": str(job.owner_id), "provider": "modal", "error_code": code})
        return failed_job

    failed_job = await mark_job_failed(
        session,
        job,
        error_code="internal_error",
        error_message="Modal inference ended without a complete event.",
    )
    await broker.publish(
        job.id,
        "error",
        ErrorEvent(
            job_id=str(job.id),
            code="internal_error",
            message="Inference ended without a complete event.",
            retryable=True,
            last_timestep=completed_timesteps - 1 if completed_timesteps > 0 else None,
        ).model_dump(mode="json"),
    )
    return failed_job


async def process_configured_inference_job(
    session: AsyncSession,
    job_id: UUID,
    broker: JobEventBroker | None = None,
) -> Job:
    from app.core.config import get_settings

    settings = get_settings()
    if settings.inference_provider == "fake":
        return await process_fake_inference_job(session, job_id, broker)
    if settings.inference_provider == "modal":
        return await process_modal_inference_job(
            session,
            job_id,
            broker,
            app_name=settings.modal_app_name,
            function_name=settings.modal_function_name,
            environment_name=settings.modal_environment_name,
            timeout_seconds=settings.modal_call_timeout_seconds,
            max_attempts=settings.modal_call_max_attempts,
        )
    raise ValueError(f"Unsupported inference provider: {settings.inference_provider}")


def decode_chunk_envelope(payload: str) -> dict:
    import base64

    import msgpack

    return msgpack.unpackb(base64.b64decode(payload), raw=False)
