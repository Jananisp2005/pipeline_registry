from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.pipeline import Pipeline
from app.schemas.pipeline import PipelineCreate, PipelineUpdate


class PipelineNotFoundError(Exception):
    pass


class PipelineNameAlreadyExistsError(Exception):
    pass


def create_pipeline(db: Session, pipeline_data: PipelineCreate) -> Pipeline:
    existing = db.query(Pipeline).filter(
        Pipeline.name == pipeline_data.name
    ).first()

    if existing:
        raise PipelineNameAlreadyExistsError(
            f"Pipeline name '{pipeline_data.name}' already exists"
        )
    
    new_pipeline = Pipeline(**pipeline_data.model_dump())

    db.add(new_pipeline)

    try:
        db.commit()
        db.refresh(new_pipeline)
    except IntegrityError as exc:
        db.rollback()

        # PostgreSQL unique constraint identifies duplicate names.
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise PipelineNameAlreadyExistsError(
                f"Pipeline name '{pipeline_data.name}' already exists"
            ) from exc

        raise

    return new_pipeline


def get_pipeline(db: Session, pipeline_id: int) -> Pipeline:
    pipeline = (
        db.query(Pipeline)
        .filter(Pipeline.id == pipeline_id)
        .first()
    )

    if pipeline is None:
        raise PipelineNotFoundError(
            f"Pipeline with ID {pipeline_id} not found"
        )

    return pipeline



def get_pipelines(
    db: Session,
    limit: int = 10,
    offset: int = 0,
    status: str | None = None,
    group_id: str | None = None,
    search: str | None = None
) -> tuple[list[Pipeline], int]:

    query = db.query(Pipeline)

    # Apply optional filters.
    if status is not None:
        query = query.filter(Pipeline.status == status)

    if group_id is not None:
        query = query.filter(Pipeline.group_id == group_id)

    if search is not None:
        query = query.filter(Pipeline.name.ilike(f"%{search}%"))

    total = query.count()

    pipelines = (
        query
        .order_by(Pipeline.created_at.desc(), Pipeline.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return pipelines, total



def update_pipeline(
    db: Session,
    pipeline_id: int,
    pipeline_data: PipelineUpdate
) -> Pipeline:

    pipeline = get_pipeline(db, pipeline_id)

    update_data = pipeline_data.model_dump(exclude_unset=True)

    if "name" in update_data:
        existing = db.query(Pipeline).filter(
            Pipeline.name == update_data["name"],
            Pipeline.id != pipeline_id
        ).first()

        if existing:
            raise PipelineNameAlreadyExistsError(
                f"Pipeline name '{update_data['name']}' already exists"
            )
    # Changing target_table is allowed for now, but existing data
    # may remain in the old table and will not move automatically.
    for key, value in update_data.items():
        setattr(pipeline, key, value)

    try:
        db.commit()
        db.refresh(pipeline)

    except IntegrityError as exc:
        db.rollback()

        if getattr(exc.orig, "sqlstate", None) == "23505":
            duplicate_name = update_data.get("name", f"pipeline ID {pipeline_id}")

            raise PipelineNameAlreadyExistsError(
                f"Pipeline name '{duplicate_name}' already exists"
            ) from exc

        raise

    return pipeline

def delete_pipeline(db: Session, pipeline_id: int) -> Pipeline:
    pipeline = get_pipeline(db, pipeline_id)

    # Soft delete: preserve the row and its history.
    pipeline.status = "inactive"

    db.commit()
    db.refresh(pipeline)

    return pipeline


def pipeline_name_exists(
    db: Session,
    name: str,
    exclude_id: int | None = None
) -> bool:

    query = db.query(Pipeline).filter(
        Pipeline.name == name
    )

    if exclude_id is not None:
        query = query.filter(Pipeline.id != exclude_id)

    return query.first() is not None
