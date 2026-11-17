from sqlalchemy import (
    Column,
    Integer,
    String,
    CheckConstraint,
    UniqueConstraint,
    DateTime,
    text
)
from sqlalchemy.sql import func

from app.database import Base


class Pipeline(Base):
    __tablename__ = "pipelines"

    __table_args__ = (
        UniqueConstraint("name", name="uq_pipelines_name"),

        CheckConstraint(
            "char_length(name) BETWEEN 3 AND 50 "
            "AND name ~ '^[a-z0-9-]+$'",
            name="ck_pipeline_name"
        ),

        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_pipeline_status"
        ),

        CheckConstraint(
            "schema_version = 'latest' OR "
            "(schema_version ~ '^[1-9][0-9]*$')",
            name="ck_pipeline_schema_version"
        ),

        CheckConstraint(
            "target_table ~ '^[a-z][a-z0-9_]{0,62}$' "
            "AND target_table NOT IN "
            "('select', 'table', 'user', 'order', 'group')",
            name="ck_pipeline_target_table"
        ),

        CheckConstraint(
            "group_id <> '' AND group_id !~ '[[:space:]]'",
            name="ck_pipeline_group_id"
        ),

        CheckConstraint(
            "artifact_id <> '' AND artifact_id !~ '[[:space:]]'",
            name="ck_pipeline_artifact_id"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(50), nullable=False, unique=True)

    description = Column(String(500), nullable=True)

    group_id = Column(String(100), nullable=False)

    artifact_id = Column(String(100), nullable=False)

    schema_version = Column(String(20), nullable=False)

    target_table = Column(String(63), nullable=False)

    status = Column(
        String(10),
        nullable=False,
        server_default=text("'active'")
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
