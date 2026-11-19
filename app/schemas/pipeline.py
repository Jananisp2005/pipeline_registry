import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


RESERVED_TABLE_NAMES = {
    "select",
    "table",
    "user",
    "order",
    "group"
}

class PipelineCreate(BaseModel):
    name: str = Field(min_length=3, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    group_id: str = Field(min_length=1, max_length=100)
    artifact_id: str = Field(min_length=1, max_length=100)
    schema_version: str
    target_table: str = Field(min_length=1, max_length=63)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9-]{3,50}", value):
            raise ValueError(
                "Name must contain only lowercase letters, digits and hyphens"
            )
        return value
 
    @field_validator("group_id", "artifact_id")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if any(char.isspace() for char in value):
            raise ValueError("Spaces are not allowed")
        return value

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        if value != "latest" and not re.fullmatch(r"[1-9][0-9]*", value):
            raise ValueError(
                "Schema version must be 'latest' or a positive whole number"
            )
        return value

    @field_validator("target_table")
    @classmethod
    def validate_target_table(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", value):
            raise ValueError(
                "Table name must start with a lowercase letter "
                "and contain only lowercase letters, digits and underscores"
            )

        if value in RESERVED_TABLE_NAMES:
            raise ValueError("This is a reserved SQL word")

        return value


class PipelineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    group_id: str | None = Field(default=None, min_length=1, max_length=100)
    artifact_id: str | None = Field(default=None, min_length=1, max_length=100)
    schema_version: str | None = None
    target_table: str | None = Field(default=None, min_length=1, max_length=63)
    status: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Name cannot be null")

        if not re.fullmatch(r"[a-z0-9-]{3,50}", value):
            raise ValueError(
                "Name must contain only lowercase letters, digits and hyphens"
            )
        return value

    @field_validator("group_id", "artifact_id")
    @classmethod
    def validate_identifier(cls, value: str | None) -> str | None:
        if value is None or any(char.isspace() for char in value):
            raise ValueError("Value is required and spaces are not allowed")
        return value

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Schema version cannot be null")

        if value != "latest" and not re.fullmatch(r"[1-9][0-9]*", value):
            raise ValueError(
                "Schema version must be 'latest' or a positive whole number"
            )
        return value

    @field_validator("target_table")
    @classmethod
    def validate_target_table(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Target table cannot be null")

        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", value):
            raise ValueError("Invalid target table name")

        if value in RESERVED_TABLE_NAMES:
            raise ValueError("This is a reserved SQL word")

        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None or value not in {"active", "inactive"}:
            raise ValueError("Status must be active or inactive")
        return value

class PipelineOut(BaseModel):
    id: int
    name: str
    description: str | None
    group_id: str
    artifact_id: str
    schema_version: str
    target_table: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PipelineListOut(BaseModel):
    items: list[PipelineOut]
    total: int
    limit: int
    offset: int
