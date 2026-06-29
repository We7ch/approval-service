from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.api.routes.approval_requests import router as approval_requests_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.logging import SafeRequestLoggingMiddleware, configure_logging

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title=settings.app_name)
app.add_middleware(SafeRequestLoggingMiddleware)
app.include_router(health_router)
app.include_router(approval_requests_router)


if settings.enable_local_start_page:
    @app.get("/", include_in_schema=False)
    def local_start_page():
        return FileResponse(settings.local_start_page_file)
