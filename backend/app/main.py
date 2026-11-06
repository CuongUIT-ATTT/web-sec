"""FastAPI application factory for the controlled authorization-testing MVP."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware

from backend.app.api.routes import router
from backend.app.api.workflow_routes import router as workflow_router
from backend.app.core.settings import Settings
from backend.app.persistence.database import create_session_factory
from backend.app.workers.service import worker_loop


def create_app(settings: Settings) -> FastAPI:
    """Create a fail-closed API whose database is initialized before serving traffic."""
    session_factory = create_session_factory(settings.database_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.session_factory = session_factory
        stop_event = asyncio.Event()
        worker_task = asyncio.create_task(worker_loop(session_factory, settings, stop_event))
        try:
            yield
        finally:
            stop_event.set()
            await worker_task

    app = FastAPI(
        title="Controlled REST Authorization Testing",
        version="0.1.0",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        https_only=settings.secure_cookies,
        same_site="strict",
        session_cookie="authz_admin_session",
    )

    @app.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(router)
    app.include_router(workflow_router)

    frontend_dist = Path(__file__).resolve().parents[2] / "frontend_dist"
    if frontend_dist.is_dir() and (frontend_dist / "index.html").is_file():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="frontend-assets")

        @app.get("/{page_path:path}", include_in_schema=False)
        def frontend(page_path: str):
            candidate = frontend_dist / page_path
            if page_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(frontend_dist / "index.html")

    return app
