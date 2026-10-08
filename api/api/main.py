from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from api.core import health, metrics
from api.core.config import get_settings
from api.core.db import get_engine
from api.core.errors import ERROR_RESPONSES, install_error_handlers
from api.core.logging import configure_logging
from api.core.middleware import RequestContextMiddleware
from api.core.redis import get_redis


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await get_engine().dispose()
    await get_redis().aclose()


def create_app() -> FastAPI:
    configure_logging(get_settings().log_level)

    app = FastAPI(title="Manga & Novel API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)

    app.include_router(health.router)
    app.include_router(metrics.router)

    # Module routers (auth, catalogue, ...) are included on this one.
    v1 = APIRouter(prefix="/v1", responses=ERROR_RESPONSES)
    app.include_router(v1)

    return app


app = create_app()
