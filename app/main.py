from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.database import Base, engine
from app.models.pipeline import Pipeline
from app.registry.client import ApicurioClient
from app.routers.pipeline import router as pipeline_router
from app.config import settings
from app.services.pipeline_service import pipeline_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:

    # Create tables that do not exist in PostgreSQL.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("Database tables created!")
    # Before yield
    pipeline_service.registry = ApicurioClient(settings)

    yield

    # After yield
    await pipeline_service.registry.close()
    await engine.dispose()
    print("shutdown")

app = FastAPI(
    title="Pipeline Registry API",
    description="API for managing pipelines",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(pipeline_router)

@app.get("/")
def home():
    return {"message": "Pipeline Registry API is running"}
