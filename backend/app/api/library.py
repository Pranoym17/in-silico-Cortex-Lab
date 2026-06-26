from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.library import LibraryDetailResponse, LibraryForkResponse, LibraryListResponse
from app.services.library import fork_library_entry, get_library_detail, list_library_entries

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


@router.post("/{slug}/fork", response_model=LibraryForkResponse)
async def fork_library_route(
    slug: str,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
):
    return await fork_library_entry(session, user, slug)
