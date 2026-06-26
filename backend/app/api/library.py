from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.library import LibraryDetailResponse, LibraryListResponse
from app.services.library import get_library_detail, list_library_entries

router = APIRouter()


@router.get("", response_model=LibraryListResponse)
async def list_library_route(
    tag: str | None = None,
    search: str | None = None,
    sort: str = Query(default="featured", pattern="^(featured|newest|run_count)$"),
    session: AsyncSession = Depends(get_db),
):
    return await list_library_entries(session, tag=tag, search=search, sort=sort)


@router.get("/{slug}", response_model=LibraryDetailResponse)
async def get_library_detail_route(
    slug: str,
    session: AsyncSession = Depends(get_db),
):
    return await get_library_detail(session, slug)
