from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, topology
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.services.topology_cache import topology_cache

configure_logging(settings.DEBUG)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("backend_startup", host=settings.HOST, port=settings.PORT)
    topology_cache.start()
    yield
    await topology_cache.stop()


app = FastAPI(
    title="Open Vision Vite Backend",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET"],  # v1.0.0 is read-only: topology + device query only
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(topology.router, prefix="/api")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
