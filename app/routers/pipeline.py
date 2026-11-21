from typing import Literal,Annotated
import json

from fastapi import APIRouter, Depends, HTTPException, Query,UploadFile,File,Path

from sqlalchemy.orm import Session

from app.database import get_db

from app.schemas.pipeline import (
    PipelineCreate,
    PipelineUpdate,
    PipelineOut,
    PipelineListOut
)

from app.registry.exception import (
    ArtifactNotFoundError,
    VersionNotFoundError,
    RegistryUnavailableError,
)
from app.schemas.pipeline import HeaderCheckResponse
from app.services.pipeline_service import pipeline_service

from app.services.exception import (
    PipelineNotFoundError,
    DuplicatePipelineError,
    SchemaNotFoundError,
    RegistryUnavailableServiceError,
)


router = APIRouter(
    prefix="/pipelines",
    tags=["Pipelines"]
)

POSTGRES_INTEGER_MAX = 2147483647

# 1. Create pipeline
@router.post("", response_model=PipelineOut, status_code=201)
def create_pipeline(
    pipeline_data: PipelineCreate,
    db: Session = Depends(get_db)
) -> PipelineOut:

    try:
        return pipeline_service.create_pipeline(
            db,
            pipeline_data
        )

    except DuplicatePipelineError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc)
        ) from exc

    except SchemaNotFoundError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc)
        ) from exc

    except RegistryUnavailableServiceError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc)
        ) from exc


# 2. List pipelines
@router.get("", response_model=PipelineListOut)
def get_pipelines(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Literal["active", "inactive"] | None = None,
    group_id: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db)
) -> PipelineListOut:

    pipelines, total = pipeline_service.get_pipelines(
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
    pipeline_id:Annotated[
       int,
       Path(ge=1, le=POSTGRES_INTEGER_MAX)
       ],
    db: Session = Depends(get_db)
) -> PipelineOut:

    try:
        return pipeline_service.get_pipeline(
            db,
            pipeline_id
        )

    except PipelineNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        ) from exc


# 4. Update pipeline
@router.patch("/{pipeline_id}", response_model=PipelineOut)
def update_pipeline(
    pipeline_id:Annotated[
    int,
    Path(ge=1, le=POSTGRES_INTEGER_MAX)],
    pipeline_data: PipelineUpdate,
    db: Session = Depends(get_db)
) -> PipelineOut:

    try:
        return pipeline_service.update_pipeline(
            db,
            pipeline_id,
            pipeline_data
        )

    except PipelineNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        ) from exc

    except DuplicatePipelineError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc)
        ) from exc

    except SchemaNotFoundError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc)
        ) from exc

    except RegistryUnavailableServiceError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc)
        ) from exc


# 5. Delete pipeline (soft delete)
@router.delete("/{pipeline_id}", response_model=PipelineOut)
def delete_pipeline(
    pipeline_id:Annotated[
    int,
    Path(ge=1, le=POSTGRES_INTEGER_MAX)],
    db: Session = Depends(get_db)
) -> PipelineOut:

    try:
        return pipeline_service.delete_pipeline(
            db,
            pipeline_id
        )

    except PipelineNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        ) from exc



@router.get("/{pipeline_id}/schema")
def get_pipeline_schema(
    pipeline_id: int ,
    db: Session = Depends(get_db)
):
    # Step 1: Get pipeline from PostgreSQL
    try:
        pipeline = pipeline_service.get_pipeline(
            db,
            pipeline_id
        )

    except PipelineNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        )

    # Step 2: Fetch schema live from Apicurio
    try:
        result = pipeline_service.registry.get_schema(
            group_id=pipeline.group_id,
            artifact_id=pipeline.artifact_id,
            version=pipeline.schema_version
        )

        # Step 3: Convert JSON string into Python dictionary
        schema = json.loads(result["schema"])

        # Step 4: Return response
        return {
            "pipeline_id": pipeline.id,
            "group_id": pipeline.group_id,
            "artifact_id": pipeline.artifact_id,
            "requested_version": pipeline.schema_version,
            "resolved_version": result["version"],
            "schema": schema
        }

    except (ArtifactNotFoundError, VersionNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    except (SchemaNotFoundError, RegistryUnavailableServiceError) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc)
        )

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=502,
            detail="Registry returned invalid JSON schema"
        )

@router.post(
    "/{pipeline_id}/check-header",
    response_model=HeaderCheckResponse
)
def check_pipeline_header(
    pipeline_id: int ,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        
       return pipeline_service.check_header(
         db,
         pipeline_id,
         file
        )

    except PipelineNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        ) from exc

    except (SchemaNotFoundError, RegistryUnavailableServiceError) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc)
        ) from exc