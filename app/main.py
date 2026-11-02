import logging
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.routers.router import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import RequestContextMiddleware, configure_logging
from app.core.ratelimit import limiter
from app.db.session import engine

DESCRIPTION = """
Backend for **Lawyer Diary**, a mobile app used only by lawyers.

Use **Authorize** (top right): enter the email as *username* and your password.

Every record is private to its owner; another lawyer's IDs return `404`.
Errors always look like `{"error": {"code", "message", "fields"}}`.

The limitation calculator is a **helper, not legal advice**.
"""

TAGS: list[dict[str, Any]] = [
    {"name": "Auth", "description": "Register, log in, refresh, log out"},
    {"name": "Me & Settings", "description": "Profile, reminder settings, change password"},
    {"name": "Dashboard & Calendar", "description": "Today screen, month dots, day list"},
    {"name": "Clients", "description": "Client directory"},
    {"name": "Cases", "description": "Cases and case detail"},
    {"name": "Hearings", "description": "Schedule, record and correct hearings"},
    {"name": "Limitation", "description": "Rules, calculator and saved deadlines"},
    {"name": "Holidays", "description": "Global (read-only) and personal holidays"},
    {"name": "Reminders", "description": "Upcoming reminders with remind_at pre-computed"},
    {"name": "System", "description": "Health check"},
]


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)

    app = FastAPI(
        title="Lawyer Diary API",
        version="1.0.0",
        description=DESCRIPTION,
        openapi_tags=TAGS,
    )
    app.state.limiter = limiter
    register_error_handlers(app)

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    app.include_router(api_router)

    @app.get("/health", tags=["System"], summary="Liveness and database connectivity")
    def health() -> JSONResponse:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            logging.getLogger("app.health").error(
                "database_unreachable", extra={"error_type": type(exc).__name__}
            )
            return JSONResponse(
                status_code=503, content={"status": "degraded", "database": "disconnected"}
            )
        return JSONResponse(content={"status": "ok", "database": "connected"})

    return app


app = create_app()