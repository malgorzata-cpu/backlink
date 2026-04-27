import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Project
from app.routes import backlinks, broken, dashboard, opportunities, projects, uploads


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Link Building Dashboard",
        description="Dashboard do wykrywania okazji linkowych z eksportów Ahrefs",
        version="0.2.0",
    )

    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.middleware("http")
    async def project_context_middleware(request: Request, call_next):
        if request.url.path.startswith(("/static", "/healthz")):
            request.state.current_project = None
            request.state.all_projects = []
            return await call_next(request)

        db = SessionLocal()
        try:
            current = None
            try:
                slug = request.cookies.get("current_project_slug")
                if slug:
                    current = db.execute(
                        select(Project).where(Project.slug == slug)
                    ).scalar_one_or_none()
                if current is None:
                    current = db.execute(
                        select(Project)
                        .order_by(Project.created_at.asc())
                        .limit(1)
                    ).scalar_one_or_none()
                all_projects = list(
                    db.execute(select(Project).order_by(Project.name)).scalars()
                )
            except Exception as e:
                # DB not migrated yet, or other transient issue. Render forms anyway.
                logger.warning("project_context_middleware failed: %s", e)
                current = None
                all_projects = []
            request.state.current_project = current
            request.state.all_projects = all_projects
        finally:
            db.close()
        return await call_next(request)

    app.include_router(projects.router)
    app.include_router(dashboard.router)
    app.include_router(opportunities.router)
    app.include_router(broken.router)
    app.include_router(backlinks.router)
    app.include_router(uploads.router)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()
