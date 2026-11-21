from sqlalchemy.orm import Session
import csv,json
from collections import Counter
from fastapi import UploadFile
from app.config import settings
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
        # Create one reusable Apicurio client
        self.registry = ApicurioClient(settings)

    # Common registry validation
    def _validate_schema(
        self,
        group_id: str,
        artifact_id: str,
        version: str
    ) -> dict:

        try:
            # Step 1: Check artifact
            exists = self.registry.artifact_exists(
                group_id,
                artifact_id
            )

            if not exists:
                raise SchemaNotFoundError(
                    f"Artifact '{artifact_id}' not found in registry"
                )

            # Step 2: Fetch requested schema version
            return self.registry.get_schema(
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
    def create_pipeline(
        self,
        db: Session,
        pipeline_data: PipelineCreate
    ):

        # Step 1: Check duplicate name in database
        if pipeline_crud.pipeline_name_exists(
            db,
            pipeline_data.name
        ):
            raise DuplicatePipelineError(
                f"Pipeline name '{pipeline_data.name}' already exists"
            )

        # Step 2 and 3: Validate artifact and schema version
        schema_result = self._validate_schema(
            pipeline_data.group_id,
            pipeline_data.artifact_id,
            pipeline_data.schema_version
        )

        # Step 4: Store actual version instead of 'latest'
        # actual_version = str(schema_result["version"])

        # pipeline_data = pipeline_data.model_copy(
        #     update={"schema_version": actual_version}
        # )

        # Step 5: Insert into database
        try:
            return pipeline_crud.create_pipeline(
                db,
                pipeline_data
            )

        except pipeline_crud.PipelineNameAlreadyExistsError as exc:
            # Handles duplicate-name race conditions
            raise DuplicatePipelineError(str(exc)) from exc

    # List pipelines
    def get_pipelines(
        self,
        db: Session,
        limit: int = 10,
        offset: int = 0,
        status: str | None = None,
        group_id: str | None = None,
        search: str | None = None
    ):

        return pipeline_crud.get_pipelines(
            db,
            limit,
            offset,
            status,
            group_id,
            search
        )

    # Get one pipeline
    def get_pipeline(
        self,
        db: Session,
        pipeline_id: int
    ):

        try:
            return pipeline_crud.get_pipeline(
                db,
                pipeline_id
            )

        except pipeline_crud.PipelineNotFoundError as exc:
            raise PipelineNotFoundError(str(exc)) from exc

    # Update pipeline
    def update_pipeline(
        self,
        db: Session,
        pipeline_id: int,
        pipeline_data: PipelineUpdate
    ):

        try:
            # First get existing pipeline
            existing = pipeline_crud.get_pipeline(
                db,
                pipeline_id
            )

        except pipeline_crud.PipelineNotFoundError as exc:
            raise PipelineNotFoundError(str(exc)) from exc

        update_data = pipeline_data.model_dump(
            exclude_unset=True
        )

        # Check duplicate name before registry validation
        if "name" in update_data:
            if pipeline_crud.pipeline_name_exists(
                db,
                update_data["name"],
                exclude_id=pipeline_id
            ):
                raise DuplicatePipelineError(
                    f"Pipeline name '{update_data['name']}' already exists"
                )

        # Validate registry only if a schema reference changes
        registry_fields = {
            "group_id",
            "artifact_id",
            "schema_version"
        }

        if registry_fields.intersection(update_data):

            # Build the final combination of registry values
            group_id = update_data.get(
                "group_id", existing.group_id
            )

            artifact_id = update_data.get(
                "artifact_id", existing.artifact_id
            )

            version = update_data.get(
                "schema_version", existing.schema_version
            )

            schema_result = self._validate_schema(
                group_id,
                artifact_id,
                version
            )

            # # Save the real version number
            # update_data["schema_version"] = str(
            #     schema_result["version"]
            # )

        # Rebuild the update schema
        updated_data = PipelineUpdate.model_validate(
            update_data
        )

        try:
            return pipeline_crud.update_pipeline(
                db,
                pipeline_id,
                updated_data
            )

        except pipeline_crud.PipelineNotFoundError as exc:
            raise PipelineNotFoundError(str(exc)) from exc

        except pipeline_crud.PipelineNameAlreadyExistsError as exc:
            raise DuplicatePipelineError(str(exc)) from exc

    # Delete pipeline (soft delete)
    def delete_pipeline(
        self,
        db: Session,
        pipeline_id: int
    ):

        try:
            return pipeline_crud.delete_pipeline(
                db,
                pipeline_id
            )

        except pipeline_crud.PipelineNotFoundError as exc:
            raise PipelineNotFoundError(str(exc)) from exc

    
    def get_pipeline_schema(
        self,
        db: Session,
        pipeline_id: int
    ) -> dict:

        # Get pipeline from database (404 if not found)
        pipeline = self.get_pipeline(db, pipeline_id)

        try:
            result = self.registry.get_schema(
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
            # Pipeline exists, but its Apicurio schema is missing.
            raise SchemaNotFoundError(
                f"Schema not found in registry: {exc}"
            ) from exc

        except RegistryUnavailableError as exc:
            raise RegistryUnavailableServiceError(
                f"Registry unavailable: {exc}"
            ) from exc

    def check_header(
       self,
       db,
       pipeline_id: int,
       file: UploadFile
     ):
        schema_response= self.get_pipeline_schema(db, pipeline_id)

        # schema_response = self.registry.get_schema(
        #         group_id=pipeline.group_id,
        #         artifact_id=pipeline.artifact_id,
        #         version=pipeline.schema_version
        # )

        schema = schema_response["schema"]


        # Convert JSON string into Python dictionary
        if isinstance(schema, str):
           schema = json.loads(schema)

    # Step 2: Extract expected column names
        expected_columns = [
              field["name"]
              for field in schema.get("fields", [])
        ]

        # print("SCHEMA:", schema)
        # print("SCHEMA TYPE:", type(schema))
        # print("SCHEMA KEYS:", schema.keys())

    # Step 3: Read ONLY the first line
        first_line = file.file.readline()

    # Step 4: Decode UTF-8 and remove BOM if present
        header_text = first_line.decode("utf-8-sig")

    # Step 5: Parse CSV header using csv module
        reader = csv.reader([header_text])

        found_columns = next(reader, [])

    # Step 6: Find missing columns
        missing = [
           column
           for column in expected_columns
           if column not in found_columns
        ]

    # Step 7: Find extra columns
        extra = [
           column
           for column in found_columns
           if column not in expected_columns
        ]

    ## Step 8: Find matching columns in expected schema order
        matches = [
           column
           for column in expected_columns
           if column in found_columns
        ]

    # Step 9: Check whether matching columns are in correct order
        common_in_file_order = [
            column for column in found_columns
            if column in expected_columns
        ]

        order_matches = bool(matches) and common_in_file_order == matches

        # Step 10: Check exact match including order
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
