from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.admin.router import router as admin_router
from api.auth.router import router as auth_router
from api.core import health, metrics
from api.core.config import get_settings
from api.core.db import get_engine
from api.core.errors import ERROR_RESPONSES, install_error_handlers
from api.core.logging import configure_logging
from api.core.middleware import RequestContextMiddleware
from api.core.redis import get_redis
from api.core.request_id import REQUEST_ID_HEADER


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await get_engine().dispose()
    await get_redis().aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="Manga & Novel API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(RequestContextMiddleware)
    # Added last, so it is outermost: even the last-resort 500 carries CORS
    # headers and the browser shows the real error instead of a CORS failure.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER, "Retry-After"],
    )
    install_error_handlers(app)

    app.include_router(health.router)
    app.include_router(metrics.router)

    v1 = APIRouter(prefix="/v1", responses=ERROR_RESPONSES)
    v1.include_router(auth_router)
    v1.include_router(admin_router)
    app.include_router(v1)

    return app


app = create_app()
