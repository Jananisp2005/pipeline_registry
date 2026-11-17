
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.pipeline import (
    PipelineCreate,
    PipelineUpdate,
    PipelineOut,
    PipelineListOut
)
from app.crud import pipeline as pipeline_crud


router = APIRouter(
    prefix="/pipelines",
    tags=["Pipelines"]
)


# 1. Create pipeline
@router.post("", response_model=PipelineOut, status_code=201)
def create_pipeline(
    pipeline_data: PipelineCreate,
    db: Session = Depends(get_db)
) -> PipelineOut:

    try:
        return pipeline_crud.create_pipeline(db, pipeline_data)

    except pipeline_crud.PipelineNameAlreadyExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc)
        ) from exc


# 2. List pipelines with pagination and filters
@router.get("", response_model=PipelineListOut)
def get_pipelines(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Literal["active", "inactive"] | None = None,
    group_id: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db)
) -> PipelineListOut:

    pipelines, total = pipeline_crud.get_pipelines(
        db=db,
        limit=limit,
        offset=offset,
        status=status,
        group_id=group_id,
        search=search
    )

    return {
        "items": pipelines,
        "total": total,
        "limit": limit,
        "offset": offset
    }


# 3. Get one pipeline
@router.get("/{pipeline_id}", response_model=PipelineOut)
def get_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db)
) -> PipelineOut:

    try:
        return pipeline_crud.get_pipeline(db, pipeline_id)

    except pipeline_crud.PipelineNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        ) from exc


# 4. Update pipeline
@router.patch("/{pipeline_id}", response_model=PipelineOut)
def update_pipeline(
    pipeline_id: int,
    pipeline_data: PipelineUpdate,
    db: Session = Depends(get_db)
) -> PipelineOut:

    try:
        return pipeline_crud.update_pipeline(
            db,
            pipeline_id,
            pipeline_data
        )

    except pipeline_crud.PipelineNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        ) from exc

    except pipeline_crud.PipelineNameAlreadyExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc)
        ) from exc


# 5. Remove pipeline (soft delete)
@router.delete("/{pipeline_id}", response_model=PipelineOut)
def delete_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db)
) -> PipelineOut:

    try:
        # Soft delete: the row remains with status inactive.
        # Repeating this request returns the already inactive pipeline.
        return pipeline_crud.delete_pipeline(db, pipeline_id)

    except pipeline_crud.PipelineNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        ) from exc
