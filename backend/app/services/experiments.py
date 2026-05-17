from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.experiment import Experiment, ExperimentStatus
from app.models.user import User
from app.schemas.experiment import ExperimentCreate, ExperimentUpdate


async def create_experiment(session: AsyncSession, owner: User, data: ExperimentCreate) -> Experiment:
    experiment = Experiment(owner_id=owner.id, name=data.name, description=data.description)
    session.add(experiment)
    await session.commit()
    await session.refresh(experiment)
    return experiment


async def list_experiments(session: AsyncSession, owner: User) -> list[Experiment]:
    result = await session.execute(
        select(Experiment)
        .where(Experiment.owner_id == owner.id)
        .where(Experiment.status != ExperimentStatus.archived)
        .order_by(Experiment.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_owned_experiment(session: AsyncSession, owner: User, experiment_id: UUID) -> Experiment:
    result = await session.execute(
        select(Experiment).where(Experiment.id == experiment_id).where(Experiment.owner_id == owner.id)
    )
    experiment = result.scalar_one_or_none()
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    return experiment


async def update_experiment(
    session: AsyncSession,
    owner: User,
    experiment_id: UUID,
    data: ExperimentUpdate,
) -> Experiment:
    experiment = await get_owned_experiment(session, owner, experiment_id)
    updates = data.model_dump(exclude_unset=True)

    for field, value in updates.items():
        setattr(experiment, field, value)

    await session.commit()
    await session.refresh(experiment)
    return experiment


async def archive_experiment(session: AsyncSession, owner: User, experiment_id: UUID) -> None:
    experiment = await get_owned_experiment(session, owner, experiment_id)
    experiment.status = ExperimentStatus.archived
    await session.commit()

