import csv,json

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import pipeline as pipeline_crud
from app.registry.client import ApicurioClient
from app.registry.exception import (
    RegistryUnavailableError,
    ArtifactNotFoundError,
    VersionNotFoundError,
)

from app.services.exception import (
    PipelineNotFoundError,
    DuplicatePipelineError,
    SchemaNotFoundError,
    RegistryUnavailableServiceError,
)

from app.schemas.pipeline import PipelineCreate, PipelineUpdate


class PipelineService:

    def __init__(self):
        # Registry client is initialized during application startup.
        self.registry: ApicurioClient | None = None

    # Common registry validation
    async def _validate_schema(
        self,
        group_id: str,
        artifact_id: str,
        version: str
    ) -> dict:

        try:
            exists = await self.registry.artifact_exists(
                group_id,
                artifact_id
            )

            if not exists:
                raise SchemaNotFoundError(
                    f"Artifact '{artifact_id}' not found in registry"
                )

            return await self.registry.get_schema(
                group_id,
                artifact_id,
                version
            )

        except (ArtifactNotFoundError, VersionNotFoundError) as exc:
            raise SchemaNotFoundError(
                f"Schema not found in registry: {exc}"
            ) from exc

        except RegistryUnavailableError as exc:
            raise RegistryUnavailableServiceError(
                f"Registry unavailable: {exc}"
            ) from exc

    # Create pipeline
    async def create_pipeline(
        self,
        db: AsyncSession,
        pipeline_data: PipelineCreate
    ):

        if await pipeline_crud.pipeline_name_exists(
            db,
            pipeline_data.name
        ):
            raise DuplicatePipelineError(
                f"Pipeline name '{pipeline_data.name}' already exists"
            )

        await self._validate_schema(
            pipeline_data.group_id,
            pipeline_data.artifact_id,
            pipeline_data.schema_version
        )

        try:
            return await pipeline_crud.create_pipeline(
                db,
                pipeline_data
            )

        except pipeline_crud.PipelineNameAlreadyExistsError as exc:
            raise DuplicatePipelineError(str(exc)) from exc

    # List pipelines
    async def get_pipelines(
        self,
        db: AsyncSession,
        limit: int = 10,
        offset: int = 0,
        status: str | None = None,
        group_id: str | None = None,
        search: str | None = None
    ):

        return await pipeline_crud.get_pipelines(
            db,
            limit,
            offset,
            status,
            group_id,
            search
        )

    # Get one pipeline
    async def get_pipeline(
        self,
        db: AsyncSession,
        pipeline_id: int
    ):

        try:
            return await pipeline_crud.get_pipeline(
                db,
                pipeline_id
            )

        except pipeline_crud.PipelineNotFoundError as exc:
            raise PipelineNotFoundError(str(exc)) from exc

    # Update pipeline
    async def update_pipeline(
        self,
        db: AsyncSession,
        pipeline_id: int,
        pipeline_data: PipelineUpdate
    ):

        try:
            existing = await pipeline_crud.get_pipeline(
                db,
                pipeline_id
            )

        except pipeline_crud.PipelineNotFoundError as exc:
            raise PipelineNotFoundError(str(exc)) from exc

        update_data = pipeline_data.model_dump(
            exclude_unset=True
        )

        if "name" in update_data:
            if await pipeline_crud.pipeline_name_exists(
                db,
                update_data["name"],
                exclude_id=pipeline_id
            ):
                raise DuplicatePipelineError(
                    f"Pipeline name '{update_data['name']}' already exists"
                )

        registry_fields = {
            "group_id",
            "artifact_id",
            "schema_version"
        }

        if registry_fields.intersection(update_data):

            group_id = update_data.get(
                "group_id", existing.group_id
            )

            artifact_id = update_data.get(
                "artifact_id", existing.artifact_id
            )

            version = update_data.get(
                "schema_version", existing.schema_version
            )

            await self._validate_schema(
                group_id,
                artifact_id,
                version
            )

        updated_data = PipelineUpdate.model_validate(
            update_data
        )

        try:
            return await pipeline_crud.update_pipeline(
                db,
                pipeline_id,
                updated_data
            )

        except pipeline_crud.PipelineNotFoundError as exc:
            raise PipelineNotFoundError(str(exc)) from exc

        except pipeline_crud.PipelineNameAlreadyExistsError as exc:
            raise DuplicatePipelineError(str(exc)) from exc

    # Delete pipeline (soft delete)
    async def delete_pipeline(
        self,
        db: AsyncSession,
        pipeline_id: int
    ):

        try:
            return await pipeline_crud.delete_pipeline(
                db,
                pipeline_id
            )

        except pipeline_crud.PipelineNotFoundError as exc:
            raise PipelineNotFoundError(str(exc)) from exc

    # Get pipeline schema
    async def get_pipeline_schema(
        self,
        db: AsyncSession,
        pipeline_id: int
    ) -> dict:

        pipeline = await self.get_pipeline(db, pipeline_id)

        try:
            result = await self.registry.get_schema(
                group_id=pipeline.group_id,
                artifact_id=pipeline.artifact_id,
                version=pipeline.schema_version
            )

            schema = result["schema"]

            if isinstance(schema, str):
                schema = json.loads(schema)

            return {
                "pipeline_id": pipeline.id,
                "group_id": pipeline.group_id,
                "artifact_id": pipeline.artifact_id,
                "requested_version": pipeline.schema_version,
                "resolved_version": result["version"],
                "schema": schema
            }

        except (ArtifactNotFoundError, VersionNotFoundError) as exc:
            raise SchemaNotFoundError(
                f"Schema not found in registry: {exc}"
            ) from exc

        except RegistryUnavailableError as exc:
            raise RegistryUnavailableServiceError(
                f"Registry unavailable: {exc}"
            ) from exc

    # Check CSV header
    async def check_header(
        self,
        db: AsyncSession,
        pipeline_id: int,
        file: UploadFile
    ):

        schema_response = await self.get_pipeline_schema(
            db,
            pipeline_id
        )

        schema = schema_response["schema"]

        if isinstance(schema, str):
            schema = json.loads(schema)

        expected_columns = [
            field["name"]
            for field in schema.get("fields", [])
        ]

        # Read the first 64 KB asynchronously.
        chunk_size = 64 * 1024
        header_data = await file.read(chunk_size)

        # If the first line is longer than 64 KB,
        # continue reading until newline or EOF.
        while b"\n" not in header_data and len(header_data) == chunk_size:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            header_data += chunk

        # Extract only the first line.
        first_line = header_data.split(b"\n", 1)[0]

        # Decode UTF-8 and remove BOM.
        header_text = first_line.decode("utf-8-sig").rstrip("\r")

        reader = csv.reader([header_text])
        found_columns = next(reader, [])

        missing = [
            column
            for column in expected_columns
            if column not in found_columns
        ]

        extra = [
            column
            for column in found_columns
            if column not in expected_columns
        ]

        matches = [
            column
            for column in expected_columns
            if column in found_columns
        ]

        common_in_file_order = [
            column
            for column in found_columns
            if column in expected_columns
        ]

        order_matches = (
            bool(matches)
            and common_in_file_order == matches
        )

        exact_match = expected_columns == found_columns

        print("EXPECTED:", expected_columns)
        print("FOUND:", found_columns)
        print("MISSING:", missing)
        print("EXTRA:", extra)
        print("ORDER MATCHES:", order_matches)

        return {
            "pipeline_id": pipeline_id,
            "matches": matches,
            "expected_columns": expected_columns,
            "found_columns": found_columns,
            "missing": missing,
            "extra": extra,
            "order_matches": order_matches,
            "exact_match": exact_match
        }


# One reusable service instance
pipeline_service = PipelineService()
