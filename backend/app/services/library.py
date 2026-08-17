from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.block import Block
from app.models.experiment import Experiment, ExperimentStatus
from app.models.job import Job
from app.models.library import LibraryEntry, LibraryFlag
from app.models.result import Result
from app.models.user import User
from app.schemas.library import (
    LibraryDetailResponse,
    LibraryForkResponse,
    LibraryListResponse,
    LibraryPublishRequest,
    LibraryEntryResponse,
    PublicEmbedResponse,
    PublicExperimentReportResponse,
    PublicAuthorResponse,
    PublicLibraryExperimentBlock,
    PublicResultResponse,
)
from app.services.experiments import get_owned_experiment


def normalize_tags(tags: list[str]) -> list[str]:
    normalized = []
    seen = set()

    for tag in tags:
        value = tag.strip().lower()
        if not value or value in seen:
            continue
        if len(value) > 64:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Tags must be 64 characters or less")
        normalized.append(value)
        seen.add(value)

    return normalized


async def publish_experiment(
    session: AsyncSession,
    owner: User,
    experiment_id: UUID,
    data: LibraryPublishRequest,
) -> LibraryEntry:
    experiment = await get_owned_experiment(session, owner, experiment_id)
    if experiment.status == ExperimentStatus.archived:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived experiments cannot be published")

    block_result = await session.execute(select(func.count(Block.id)).where(Block.experiment_id == experiment.id))
    if block_result.scalar_one() == 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Add at least one stimulus block before publishing")

    existing_slug_result = await session.execute(select(LibraryEntry).where(LibraryEntry.slug == data.slug))
    existing_slug = existing_slug_result.scalar_one_or_none()
    if existing_slug is not None and existing_slug.experiment_id != experiment.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Library slug is already taken")

    entry_result = await session.execute(select(LibraryEntry).where(LibraryEntry.experiment_id == experiment.id))
    entry = entry_result.scalar_one_or_none()
    now = datetime.now(UTC)

    if entry is None:
        entry = LibraryEntry(
            experiment_id=experiment.id,
            owner_id=owner.id,
            slug=data.slug,
            title=data.title,
            description=data.description,
            tags=normalize_tags(data.tags),
            published_at=now,
        )
        session.add(entry)
    else:
        entry.slug = data.slug
        entry.title = data.title
        entry.description = data.description
        entry.tags = normalize_tags(data.tags)

    experiment.is_public = True
    experiment.slug = data.slug

    await session.commit()
    await session.refresh(entry)
    return entry


async def list_library_entries(
    session: AsyncSession,
    *,
    tag: str | None = None,
    search: str | None = None,
    sort: str = "featured",
) -> LibraryListResponse:
    query = select(LibraryEntry, User).join(User, User.id == LibraryEntry.owner_id).where(LibraryEntry.moderation_status == "published")

    if tag:
        query = query.where(LibraryEntry.tags.any(tag.strip().lower()))

    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                LibraryEntry.title.ilike(term),
                LibraryEntry.description.ilike(term),
                LibraryEntry.slug.ilike(term),
            )
        )

    if sort == "run_count":
        query = query.order_by(LibraryEntry.run_count.desc(), LibraryEntry.published_at.desc())
    elif sort == "newest":
        query = query.order_by(LibraryEntry.published_at.desc())
    else:
        query = query.order_by(LibraryEntry.featured.desc(), LibraryEntry.published_at.desc())

    result = await session.execute(query.limit(50))
    return LibraryListResponse(items=[public_entry_response(entry) for entry, _owner in result.all()])


async def get_library_detail(session: AsyncSession, slug: str) -> LibraryDetailResponse:
    entry = await get_library_entry_by_slug(session, slug)
    owner_result = await session.execute(select(User).where(User.id == entry.owner_id))
    owner = owner_result.scalar_one_or_none()
    if owner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library author not found")

    experiment_result = await session.execute(select(Experiment).where(Experiment.id == entry.experiment_id))
    experiment = experiment_result.scalar_one_or_none()
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library experiment not found")

    block_result = await session.execute(select(Block).where(Block.experiment_id == experiment.id).order_by(Block.start_ms))
    blocks = [
        PublicLibraryExperimentBlock(
            id=block.id,
            type=block.type.value,
            condition=block.condition,
            start_ms=block.start_ms,
            duration_ms=block.duration_ms,
            payload=public_block_payload(block.type.value, block.payload),
        )
        for block in block_result.scalars().all()
    ]
    return LibraryDetailResponse(
        entry=public_entry_response(entry),
        author=public_author_response(owner),
        experiment_name=experiment.name,
        experiment_description=experiment.description,
        blocks=blocks,
    )


def public_entry_response(entry: LibraryEntry) -> LibraryEntryResponse:
    """Return only fields intended for anonymous public discovery."""
    return LibraryEntryResponse(
        id=entry.id,
        slug=entry.slug,
        title=entry.title,
        description=entry.description,
        tags=entry.tags,
        featured=entry.featured,
        run_count=entry.run_count,
        published_at=entry.published_at,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def public_author_response(owner: User) -> PublicAuthorResponse:
    name = (owner.display_name or "").strip()
    return PublicAuthorResponse(display_name=name or "Cortex Lab researcher", avatar_url=owner.avatar_url)


def public_block_payload(block_type: str, payload: dict) -> dict:
    """Expose presentation data without leaking private media object locations."""
    if block_type == "text":
        return {key: payload[key] for key in ("text", "voice", "display_mode") if key in payload}
    if block_type == "image":
        return {key: payload[key] for key in ("alt", "display_mode", "side_by_side") if key in payload}
    if block_type in {"audio", "video"}:
        return {key: payload[key] for key in ("title", "transcript", "trim_start_ms", "trim_end_ms") if key in payload}
    return {}


async def get_public_result(session: AsyncSession, slug: str) -> PublicResultResponse:
    result, job = await get_public_result_record(session, slug)
    return public_result_response(result, job)


async def get_public_result_record(session: AsyncSession, slug: str) -> tuple[Result, Job]:
    entry = await get_library_entry_by_slug(session, slug)
    query = (
        select(Result, Job)
        .join(Job, Job.id == Result.job_id)
        .where(Result.experiment_id == entry.experiment_id)
        .order_by(Result.created_at.desc())
        .limit(1)
    )
    row = (await session.execute(query)).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No public result is available for this experiment")
    return row


async def get_public_report(session: AsyncSession, slug: str) -> PublicExperimentReportResponse:
    detail = await get_library_detail(session, slug)
    try:
        result = await get_public_result(session, slug)
    except HTTPException as exc:
        if exc.status_code != status.HTTP_404_NOT_FOUND:
            raise
        result = None
    return PublicExperimentReportResponse(
        slug=detail.entry.slug,
        title=detail.entry.title,
        description=detail.experiment_description,
        author=detail.author,
        published_at=detail.entry.published_at,
        tags=detail.entry.tags,
        blocks=detail.blocks,
        result=result,
        limitations=[
            "Predictions are simulated average-subject responses, not measured fMRI data.",
            "Results are research outputs and must not be used for clinical or diagnostic decisions.",
        ],
    )


async def get_public_embed(session: AsyncSession, slug: str) -> PublicEmbedResponse:
    entry = await get_library_entry_by_slug(session, slug)
    result_exists = (await session.execute(select(Result.id).where(Result.experiment_id == entry.experiment_id).limit(1))).scalar_one_or_none()
    return PublicEmbedResponse(slug=entry.slug, title=entry.title, iframe_path=f"/embed/{entry.slug}", viewer_available=result_exists is not None)


def public_result_response(result: Result, job: Job) -> PublicResultResponse:
    metadata = {
        key: value
        for key, value in result.metadata_json.items()
        if key in {"processing_version", "stimulus_hash", "model_version", "sample_rate_hz", "hrf_offset_seconds", "vertex_space"}
    }
    return PublicResultResponse(
        format=result.format,
        dtype=result.dtype,
        shape=result.shape,
        vertex_count=result.vertex_count,
        timestep_count=result.timestep_count,
        sample_rate_hz=result.sample_rate_hz,
        model_name=result.model_name,
        model_version=result.model_version,
        metadata=metadata,
        completed_at=job.completed_at,
    )


async def fork_library_entry(session: AsyncSession, owner: User, slug: str) -> LibraryForkResponse:
    entry = await get_library_entry_by_slug(session, slug)

    experiment_result = await session.execute(select(Experiment).where(Experiment.id == entry.experiment_id))
    source = experiment_result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library experiment not found")

    block_result = await session.execute(select(Block).where(Block.experiment_id == source.id).order_by(Block.start_ms))
    source_blocks = list(block_result.scalars().all())

    fork = Experiment(
        owner_id=owner.id,
        name=f"{source.name} (Fork)",
        description=source.description,
        status=ExperimentStatus.draft,
        is_public=False,
        slug=None,
    )
    session.add(fork)
    await session.flush()

    for block in source_blocks:
        session.add(
            Block(
                experiment_id=fork.id,
                type=block.type,
                condition=block.condition,
                start_ms=block.start_ms,
                duration_ms=block.duration_ms,
                content_hash=block.content_hash,
                payload=deepcopy(block.payload),
            )
        )

    entry.run_count += 1
    await session.commit()
    await session.refresh(fork)
    return LibraryForkResponse(experiment_id=fork.id)


async def get_library_entry_by_slug(session: AsyncSession, slug: str) -> LibraryEntry:
    result = await session.execute(select(LibraryEntry).where(LibraryEntry.slug == slug, LibraryEntry.moderation_status == "published"))
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library entry not found")
    return entry


async def flag_library_entry(session: AsyncSession, reporter: User, slug: str, reason: str) -> LibraryFlag:
    entry = await get_library_entry_by_slug(session, slug)
    flag = LibraryFlag(entry_id=entry.id, reporter_id=reporter.id, reason=reason.strip())
    session.add(flag)
    await session.commit()
    await session.refresh(flag)
    return flag


async def list_open_library_flags(session: AsyncSession) -> list[LibraryFlag]:
    result = await session.execute(select(LibraryFlag).where(LibraryFlag.status == "open").order_by(LibraryFlag.created_at.asc()))
    return list(result.scalars().all())


async def get_library_entry_for_admin(session: AsyncSession, entry_id: UUID) -> LibraryEntry:
    result = await session.execute(select(LibraryEntry).where(LibraryEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library entry not found")
    return entry


async def get_library_flag_for_admin(session: AsyncSession, flag_id: UUID) -> LibraryFlag:
    result = await session.execute(select(LibraryFlag).where(LibraryFlag.id == flag_id))
    flag = result.scalar_one_or_none()
    if flag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library flag not found")
    return flag
