from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.pipeline import Pipeline
from app.schemas.pipeline import PipelineCreate, PipelineUpdate


class PipelineNotFoundError(Exception):
    pass


class PipelineNameAlreadyExistsError(Exception):
    pass


async def create_pipeline(
    db: AsyncSession,
    pipeline_data: PipelineCreate
) -> Pipeline:

    result = await db.execute(
        select(Pipeline).where(
            Pipeline.name == pipeline_data.name
        )
    )
    existing = result.scalars().first()

    if existing:
        raise PipelineNameAlreadyExistsError(
            f"Pipeline name '{pipeline_data.name}' already exists"
        )

    new_pipeline = Pipeline(**pipeline_data.model_dump())

    db.add(new_pipeline)

    try:
        await db.commit()
        await db.refresh(new_pipeline)

    except IntegrityError as exc:
        await db.rollback()

        # PostgreSQL unique constraint identifies duplicate names.
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise PipelineNameAlreadyExistsError(
                f"Pipeline name '{pipeline_data.name}' already exists"
            ) from exc

        raise

    return new_pipeline


async def get_pipeline(
    db: AsyncSession,
    pipeline_id: int
) -> Pipeline:

    result = await db.execute(
        select(Pipeline).where(
            Pipeline.id == pipeline_id
        )
    )
    pipeline = result.scalars().first()

    if pipeline is None:
        raise PipelineNotFoundError(
            f"Pipeline with ID {pipeline_id} not found"
        )

    return pipeline


async def get_pipelines(
    db: AsyncSession,
    limit: int = 10,
    offset: int = 0,
    status: str | None = None,
    group_id: str | None = None,
    search: str | None = None
) -> tuple[list[Pipeline], int]:

    query = select(Pipeline)

    # Apply optional filters.
    if status is not None:
        query = query.where(Pipeline.status == status)

    if group_id is not None:
        query = query.where(Pipeline.group_id == group_id)

    if search is not None:
        query = query.where(Pipeline.name.ilike(f"%{search}%"))

    # Total count with the same filters.
    count_query = select(func.count()).select_from(Pipeline)

    if status is not None:
        count_query = count_query.where(Pipeline.status == status)

    if group_id is not None:
        count_query = count_query.where(Pipeline.group_id == group_id)

    if search is not None:
        count_query = count_query.where(
            Pipeline.name.ilike(f"%{search}%")
        )

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Fetch paginated pipelines.
    query = (
        query
        .order_by(Pipeline.created_at.desc(), Pipeline.id.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(query)
    pipelines = result.scalars().all()

    return list(pipelines), total


async def update_pipeline(
    db: AsyncSession,
    pipeline_id: int,
    pipeline_data: PipelineUpdate
) -> Pipeline:

    pipeline = await get_pipeline(db, pipeline_id)

    update_data = pipeline_data.model_dump(exclude_unset=True)

    if "name" in update_data:
        result = await db.execute(
            select(Pipeline).where(
                Pipeline.name == update_data["name"],
                Pipeline.id != pipeline_id
            )
        )
        existing = result.scalars().first()

        if existing:
            raise PipelineNameAlreadyExistsError(
                f"Pipeline name '{update_data['name']}' already exists"
            )

    # Changing target_table is allowed for now, but existing data
    # may remain in the old table and will not move automatically.
    for key, value in update_data.items():
        setattr(pipeline, key, value)

    try:
        await db.commit()
        await db.refresh(pipeline)

    except IntegrityError as exc:
        await db.rollback()

        if getattr(exc.orig, "sqlstate", None) == "23505":
            duplicate_name = update_data.get(
                "name", f"pipeline ID {pipeline_id}"
            )

            raise PipelineNameAlreadyExistsError(
                f"Pipeline name '{duplicate_name}' already exists"
            ) from exc

        raise

    return pipeline


async def delete_pipeline(
    db: AsyncSession,
    pipeline_id: int
) -> Pipeline:

    pipeline = await get_pipeline(db, pipeline_id)

    # Soft delete: preserve the row and its history.
    pipeline.status = "inactive"

    await db.commit()
    await db.refresh(pipeline)

    return pipeline


async def pipeline_name_exists(
    db: AsyncSession,
    name: str,
    exclude_id: int | None = None
) -> bool:

    query = select(Pipeline).where(
        Pipeline.name == name
    )

    if exclude_id is not None:
        query = query.where(Pipeline.id != exclude_id)

    result = await db.execute(query)

    return result.scalars().first() is not None
