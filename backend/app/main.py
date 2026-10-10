"""Preserved foundation with Part 2 database readiness and authentication."""
import logging
from contextlib import asynccontextmanager
from uuid import uuid4
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from .config import Settings
from .database import install_database, schema_ready
from .auth import router, clear_cookie
from .documents import router as documents_router
from .search_api import router as search_router
from .ask_api import router as ask_router
from .ocr_api import router as ocr_router
from .feedback_api import router as feedback_router
from .analytics_api import router as analytics_router
from .request_limits import BodyLimitMiddleware, StrictHostMiddleware

logger = logging.getLogger(__name__)


class LiveResponse(BaseModel):
    status: str
    project_id: str
    phase: int


class ReadyResponse(LiveResponse):
    required_dependencies: dict[str, str]
    optional_services: dict[str, str]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    @asynccontextmanager
    async def lifespan(application):
        yield
        if application.state.engine is not None:
            application.state.engine.dispose()

    app = FastAPI(title=settings.app_name, version="0.12.0", lifespan=lifespan)
    app.state.settings = settings
    install_database(app, settings)
    app.include_router(router)
    app.include_router(documents_router)
    app.include_router(search_router)
    app.include_router(ask_router)
    app.include_router(ocr_router)
    app.include_router(feedback_router)
    app.include_router(analytics_router)

    def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
        request_id = request.state.request_id
        return JSONResponse(
            status_code=status,
            content={"error": {"code": code, "message": message, "request_id": request_id}},
            headers={"X-Request-ID": request_id},
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        # Generate our own ID: arbitrary client headers are untrusted.
        request.state.request_id = str(uuid4())
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error("Unhandled error type=%s id=%s", type(exc).__name__, request.state.request_id)
            response = error_response(request, 500, "internal_error", "An unexpected error occurred")
        if request.url.path == "/auth/refresh" and response.status_code == 401:
            clear_cookie(response, settings)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        response = error_response(request, exc.status_code, "http_error", str(exc.detail))
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Do not reflect submitted values or potentially sensitive validation input.
        return error_response(request, 422, "validation_error", "Request validation failed")

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        return error_response(request, 503, "database_unavailable", "Database service is unavailable")

    @app.get("/health/live", response_model=LiveResponse)
    async def live():
        return LiveResponse(status="alive", project_id="GOV-CS-028", phase=12)

    @app.get("/health/ready", response_model=ReadyResponse)
    def ready():
        database_ok = schema_ready(app.state.engine)
        auth_ok = settings.jwt_secret is not None
        data = ReadyResponse(
            status="ready" if database_ok and auth_ok else "not_ready", project_id="GOV-CS-028", phase=12,
            required_dependencies={"configuration": "validated",
                                   "postgresql": "connected_schema_current" if database_ok else "unavailable_or_migrations_missing",
                                   "authentication": "configured" if auth_ok else "unconfigured"},
            optional_services={"chroma": "separate_index_service", "ollama": "separate_local_rag_worker"})
        return JSONResponse(status_code=200 if database_ok and auth_ok else 503, content=data.model_dump())

    app.add_middleware(BodyLimitMiddleware, upload_path='/admin/documents/upload')
    hosts = {'127.0.0.1', 'localhost'} | {urlsplit(origin).hostname for origin in settings.cors_origins}
    app.add_middleware(StrictHostMiddleware, allowed_hosts=sorted(hosts), www_redirect=False)
    # Keep CORS outermost so even error responses have the allowed CORS headers.
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"], allow_headers=["Accept", "Content-Type", "Authorization", "X-CSRF-Protection", "X-Document-Metadata"],
        expose_headers=["X-Request-ID"],
    )
    return app


app = create_app()
