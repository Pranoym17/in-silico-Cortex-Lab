import asyncio

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.sse import encode_sse

router = APIRouter()


@router.get("/{job_id}/stream")
async def stream_job(job_id: str, from_timestep: int = 0) -> StreamingResponse:
    async def events():
        yield encode_sse("queued", {"job_id": job_id, "status": "queued"}, event_id=1)
        await asyncio.sleep(0.05)
        yield encode_sse(
            "warming",
            {"job_id": job_id, "reason": "modal_cold_start", "estimated_seconds": 90},
            event_id=2,
        )
        await asyncio.sleep(0.05)
        yield encode_sse(
            "progress",
            {
                "job_id": job_id,
                "completed_blocks": 0,
                "total_blocks": 0,
                "completed_timesteps": from_timestep,
            },
            event_id=3,
        )

    return StreamingResponse(events(), media_type="text/event-stream")

