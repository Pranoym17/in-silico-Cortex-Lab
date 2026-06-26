from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.block import Block
from app.models.experiment import Experiment, ExperimentStatus
from app.models.library import LibraryEntry
from app.models.user import User
from app.schemas.library import (
    LibraryDetailResponse,
    LibraryForkResponse,
    LibraryListResponse,
    LibraryPublishRequest,
    PublicLibraryExperimentBlock,
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
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tags must be 64 characters or less")
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
    query = select(LibraryEntry)

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
    return LibraryListResponse(items=list(result.scalars().all()))


async def get_library_detail(session: AsyncSession, slug: str) -> LibraryDetailResponse:
    entry = await get_library_entry_by_slug(session, slug)

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
            payload=block.payload,
        )
        for block in block_result.scalars().all()
    ]
    return LibraryDetailResponse(
        entry=entry,
        experiment_name=experiment.name,
        experiment_description=experiment.description,
        blocks=blocks,
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
    result = await session.execute(select(LibraryEntry).where(LibraryEntry.slug == slug))
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library entry not found")
    return entry
