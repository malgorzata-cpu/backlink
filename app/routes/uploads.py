from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import PROJECT_ROOT
from app.db import get_db
from app.models import ImportRun
from app.services.csv_import import SOURCE_REGISTRY, import_file
from app.templating import templates

router = APIRouter()

UPLOADS_DIR = PROJECT_ROOT / "data" / "uploads"


@router.get("/upload", response_class=HTMLResponse)
def upload_form(request: Request, error: str | None = None, success: str | None = None):
    return templates.TemplateResponse(
        "upload.html",
        {
            "request": request,
            "source_types": list(SOURCE_REGISTRY.keys()),
            "error": error,
            "success": success,
        },
    )


@router.post("/upload")
def upload_post(
    request: Request,
    source_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if source_type not in SOURCE_REGISTRY:
        return RedirectResponse(
            url=f"/upload?error=Unknown+source+type:+{source_type}",
            status_code=303,
        )

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = Path(file.filename or "upload.csv").name
    dest = UPLOADS_DIR / f"{timestamp}_{safe_name}"

    with open(dest, "wb") as out:
        out.write(file.file.read())

    try:
        run = import_file(db, dest, source_type)
    except Exception as e:
        return RedirectResponse(
            url=f"/upload?error=Import+failed:+{type(e).__name__}",
            status_code=303,
        )

    target = {
        "link_intersect": "/opportunities",
        "broken_backlinks": "/broken-backlinks",
        "active_backlinks": "/backlinks",
    }.get(source_type, "/")
    return RedirectResponse(
        url=f"{target}?",
        status_code=303,
        headers={"X-Import-Rows": str(run.row_count or 0)},
    )


@router.get("/imports", response_class=HTMLResponse)
def list_imports(request: Request, db: Session = Depends(get_db)):
    runs = (
        db.execute(select(ImportRun).order_by(ImportRun.started_at.desc()))
        .scalars()
        .all()
    )
    return templates.TemplateResponse(
        "imports.html",
        {"request": request, "runs": runs},
    )
