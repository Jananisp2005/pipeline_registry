from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.database import Base, engine
from app.models.pipeline import Pipeline
from app.routers.pipeline import router as pipeline_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:

    # Create tables that do not exist in PostgreSQL.
    Base.metadata.create_all(bind=engine)
    print("Database tables created!")

    yield

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
