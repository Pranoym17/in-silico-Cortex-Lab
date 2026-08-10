from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.library import AdminLibraryEntryUpdate, AdminLibraryFlagResponse, AdminLibraryFlagUpdate, LibraryEntryResponse
from app.services.library import get_library_entry_for_admin, get_library_flag_for_admin, list_open_library_flags, public_entry_response

router = APIRouter()


@router.get("/library/flags", response_model=list[AdminLibraryFlagResponse])
async def list_library_flags_route(_: User = Depends(require_admin), session: AsyncSession = Depends(get_db)):
    return await list_open_library_flags(session)


@router.patch("/library/entries/{entry_id}", response_model=LibraryEntryResponse)
async def update_library_entry_route(
    entry_id: UUID,
    body: AdminLibraryEntryUpdate,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    entry = await get_library_entry_for_admin(session, entry_id)
    if body.featured is not None:
        entry.featured = body.featured
    if body.moderation_status is not None:
        entry.moderation_status = body.moderation_status
    await session.commit()
    await session.refresh(entry)
    return public_entry_response(entry)


@router.patch("/library/flags/{flag_id}", response_model=AdminLibraryFlagResponse)
async def update_library_flag_route(
    flag_id: UUID,
    body: AdminLibraryFlagUpdate,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    flag = await get_library_flag_for_admin(session, flag_id)
    flag.status = body.status
    flag.admin_note = body.admin_note
    await session.commit()
    await session.refresh(flag)
    return flag
