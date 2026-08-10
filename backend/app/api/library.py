from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.library import LibraryDetailResponse, LibraryFlagRequest, LibraryFlagResponse, LibraryForkResponse, LibraryListResponse, PublicEmbedResponse, PublicExperimentReportResponse, PublicResultResponse
from app.services.library import flag_library_entry, fork_library_entry, get_library_detail, get_public_embed, get_public_report, get_public_result, list_library_entries

router = APIRouter()


@router.get("", response_model=LibraryListResponse)
async def list_library_route(
    tag: str | None = None,
    search: str | None = None,
    sort: str = Query(default="featured", pattern="^(featured|newest|run_count)$"),
    session: AsyncSession = Depends(get_db),
):
    return await list_library_entries(session, tag=tag, search=search, sort=sort)


@router.get("/{slug}/result", response_model=PublicResultResponse)
async def get_public_result_route(slug: str, session: AsyncSession = Depends(get_db)):
    return await get_public_result(session, slug)


@router.get("/{slug}/report", response_model=PublicExperimentReportResponse)
async def get_public_report_route(slug: str, session: AsyncSession = Depends(get_db)):
    return await get_public_report(session, slug)


@router.get("/{slug}/embed", response_model=PublicEmbedResponse)
async def get_public_embed_route(slug: str, session: AsyncSession = Depends(get_db)):
    return await get_public_embed(session, slug)


@router.post("/{slug}/flags", response_model=LibraryFlagResponse, status_code=201)
async def flag_library_route(
    slug: str,
    body: LibraryFlagRequest,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
):
    flag = await flag_library_entry(session, user, slug, body.reason)
    return LibraryFlagResponse(id=flag.id, status=flag.status)


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
