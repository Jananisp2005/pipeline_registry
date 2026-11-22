from typing import Literal, Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    UploadFile,
    File,
    Path
)

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

from app.schemas.pipeline import (
    PipelineCreate,
    PipelineUpdate,
    PipelineOut,
    PipelineListOut,
    HeaderCheckResponse
)

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
async def create_pipeline(
    pipeline_data: PipelineCreate,
    db: AsyncSession = Depends(get_db)
) -> PipelineOut:

    try:
        return await pipeline_service.create_pipeline(
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
async def get_pipelines(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Literal["active", "inactive"] | None = None,
    group_id: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db)
) -> PipelineListOut:

    pipelines, total = await pipeline_service.get_pipelines(
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
async def get_pipeline(
    pipeline_id: Annotated[
        int,
        Path(ge=1, le=POSTGRES_INTEGER_MAX)
    ],
    db: AsyncSession = Depends(get_db)
) -> PipelineOut:

    try:
        return await pipeline_service.get_pipeline(
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
async def update_pipeline(
    pipeline_id: Annotated[
        int,
        Path(ge=1, le=POSTGRES_INTEGER_MAX)
    ],
    pipeline_data: PipelineUpdate,
    db: AsyncSession = Depends(get_db)
) -> PipelineOut:

    try:
        return await pipeline_service.update_pipeline(
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
async def delete_pipeline(
    pipeline_id: Annotated[
        int,
        Path(ge=1, le=POSTGRES_INTEGER_MAX)
    ],
    db: AsyncSession = Depends(get_db)
) -> PipelineOut:

    try:
        return await pipeline_service.delete_pipeline(
            db,
            pipeline_id
        )

    except PipelineNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        ) from exc


# 6. Get schema
@router.get("/{pipeline_id}/schema")
async def get_pipeline_schema(
    pipeline_id: int,
    db: AsyncSession = Depends(get_db)
):

    try:
        return await pipeline_service.get_pipeline_schema(
            db,
            pipeline_id
        )

    except PipelineNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        ) from exc

    except SchemaNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        )

    except RegistryUnavailableServiceError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc)
        ) from exc


# 7. Check CSV header
@router.post(
    "/{pipeline_id}/check-header",
    response_model=HeaderCheckResponse
)
async def check_pipeline_header(
    pipeline_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):

    try:
        return await pipeline_service.check_header(
            db,
            pipeline_id,
            file
        )

    except PipelineNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        ) from exc

    except SchemaNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        ) from exc

    except RegistryUnavailableServiceError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc)
        ) from exc
