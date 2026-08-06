from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, devices, health, topology
from app.core.config import settings
from app.core.db import close_db, init_db
from app.core.logging import configure_logging, get_logger
from app.services.topology_cache import topology_cache

configure_logging(settings.DEBUG)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("backend_startup", host=settings.HOST, port=settings.PORT)
    await init_db()
    topology_cache.start()
    yield
    await topology_cache.stop()
    await close_db()


app = FastAPI(
    title="Open Vision Vite Backend",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    # No cookies are used (see auth_service.py docstring on bearer tokens
    # over cookies) so allow_credentials stays False even now that login
    # exists — the Authorization header doesn't require it.
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(topology.router, prefix="/api")
app.include_router(devices.router, prefix="/api")
app.include_router(auth.router, prefix="/api")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
