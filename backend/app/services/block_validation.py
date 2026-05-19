from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status

from app.models.block import BlockType

MAX_BLOCKS_PER_EXPERIMENT = 50
MAX_EXPERIMENT_DURATION_MS = 300000


@dataclass(frozen=True)
class TimelineBlock:
    id: UUID | None
    type: BlockType
    start_ms: int
    duration_ms: int


def validate_timeline(blocks: list[TimelineBlock]) -> None:
    if len(blocks) > MAX_BLOCKS_PER_EXPERIMENT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"experiments cannot exceed {MAX_BLOCKS_PER_EXPERIMENT} blocks",
        )

    sorted_blocks = sorted(blocks, key=lambda block: block.start_ms)
    previous_end = 0
    for block in sorted_blocks:
        block_end = block.start_ms + block.duration_ms
        if block.start_ms < previous_end:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="stimulus blocks cannot overlap")
        if block_end > MAX_EXPERIMENT_DURATION_MS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"experiment duration cannot exceed {MAX_EXPERIMENT_DURATION_MS}ms",
            )

        previous_end = block_end


def to_timeline_block(block) -> TimelineBlock:
    return TimelineBlock(
        id=getattr(block, "id", None),
        type=block.type,
        start_ms=block.start_ms,
        duration_ms=block.duration_ms,
    )

