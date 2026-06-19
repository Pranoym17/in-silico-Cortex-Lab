from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.block import Block
from app.models.experiment import ExperimentStatus
from app.models.user import User
from app.schemas.block import BlockCreate, BlockReorderRequest, BlockUpdate
from app.services.block_validation import TimelineBlock, to_timeline_block, validate_timeline
from app.services.experiments import get_owned_experiment


def ensure_experiment_is_editable(experiment) -> None:
    if experiment.status == ExperimentStatus.archived:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived experiments cannot be edited")


def _expected_upload_prefix(owner: User, experiment_id: UUID) -> str:
    return f"uploads/{owner.id}/experiments/{experiment_id}/"


def validate_block_content(block: Block, owner: User | None = None) -> None:
    if block.type.value == "image" and not 500 <= block.duration_ms <= 30000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="image block duration must be between 500ms and 30000ms",
        )

    if block.type.value == "audio" and block.duration_ms > 60000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="audio block duration cannot exceed 60000ms",
        )

    if block.type.value in {"image", "audio"}:
        s3_key = block.payload.get("s3_key")
        if s3_key is not None:
            if not isinstance(s3_key, str) or not s3_key.strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"{block.type.value} blocks require a valid s3_key",
                )
            if owner is not None:
                expected_prefix = _expected_upload_prefix(owner, block.experiment_id)
                if not s3_key.startswith(expected_prefix):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="block media must reference an upload owned by this experiment",
                    )

    text = block.payload.get("text") if block.type.value == "text" else None
    if isinstance(text, str) and len(text.split()) > 1024:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="text blocks cannot exceed 1024 words",
        )


async def list_blocks(session: AsyncSession, owner: User, experiment_id: UUID) -> list[Block]:
    await get_owned_experiment(session, owner, experiment_id)
    result = await session.execute(select(Block).where(Block.experiment_id == experiment_id).order_by(Block.start_ms))
    return list(result.scalars().all())


async def get_owned_block(session: AsyncSession, owner: User, experiment_id: UUID, block_id: UUID) -> Block:
    await get_owned_experiment(session, owner, experiment_id)
    result = await session.execute(
        select(Block).where(Block.experiment_id == experiment_id).where(Block.id == block_id)
    )
    block = result.scalar_one_or_none()
    if block is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block not found")
    return block


async def create_block(session: AsyncSession, owner: User, experiment_id: UUID, data: BlockCreate) -> Block:
    experiment = await get_owned_experiment(session, owner, experiment_id)
    ensure_experiment_is_editable(experiment)

    existing_blocks = await list_blocks(session, owner, experiment_id)
    candidate = TimelineBlock(id=None, type=data.type, start_ms=data.start_ms, duration_ms=data.duration_ms)
    validate_timeline([to_timeline_block(block) for block in existing_blocks] + [candidate])

    block = Block(
        experiment_id=experiment_id,
        type=data.type,
        condition=data.condition,
        start_ms=data.start_ms,
        duration_ms=data.duration_ms,
        content_hash=data.content_hash,
        payload=data.payload,
    )
    validate_block_content(block, owner)
    session.add(block)
    await session.commit()
    await session.refresh(block)
    return block


async def update_block(
    session: AsyncSession,
    owner: User,
    experiment_id: UUID,
    block_id: UUID,
    data: BlockUpdate,
) -> Block:
    experiment = await get_owned_experiment(session, owner, experiment_id)
    ensure_experiment_is_editable(experiment)
    block = await get_owned_block(session, owner, experiment_id, block_id)

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(block, field, value)

    blocks = await list_blocks(session, owner, experiment_id)
    validate_block_content(block, owner)
    validate_timeline([to_timeline_block(item) for item in blocks])

    await session.commit()
    await session.refresh(block)
    return block


async def delete_block(session: AsyncSession, owner: User, experiment_id: UUID, block_id: UUID) -> None:
    experiment = await get_owned_experiment(session, owner, experiment_id)
    ensure_experiment_is_editable(experiment)
    block = await get_owned_block(session, owner, experiment_id, block_id)
    await session.delete(block)
    await session.commit()


async def reorder_blocks(
    session: AsyncSession,
    owner: User,
    experiment_id: UUID,
    data: BlockReorderRequest,
) -> list[Block]:
    experiment = await get_owned_experiment(session, owner, experiment_id)
    ensure_experiment_is_editable(experiment)

    blocks = await list_blocks(session, owner, experiment_id)
    block_by_id = {block.id: block for block in blocks}

    missing_ids = [item.id for item in data.blocks if item.id not in block_by_id]
    if missing_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more blocks were not found")

    for item in data.blocks:
        block_by_id[item.id].start_ms = item.start_ms
        block_by_id[item.id].duration_ms = item.duration_ms

    validate_timeline([to_timeline_block(block) for block in blocks])

    await session.commit()
    for block in blocks:
        await session.refresh(block)
    return sorted(blocks, key=lambda block: block.start_ms)
