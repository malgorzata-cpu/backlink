from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routes import backlinks, broken, dashboard, opportunities, uploads


def create_app() -> FastAPI:
    app = FastAPI(
        title="Link Building Dashboard",
        description="Dashboard do wykrywania okazji linkowych z eksportów Ahrefs",
        version="0.1.0",
    )

    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

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
