from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import BrokenBacklink
from app.services.pagination import paginate
from app.templating import templates

router = APIRouter()


@router.get("/broken-backlinks", response_class=HTMLResponse)
def list_broken(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    current = getattr(request.state, "current_project", None)
    if current is None:
        return RedirectResponse(url="/projects/new", status_code=303)

    stmt = (
        select(BrokenBacklink)
        .where(BrokenBacklink.project_id == current.id)
        .order_by(
            BrokenBacklink.domain_traffic.desc().nullslast(),
            BrokenBacklink.id.asc(),
        )
    )
    page_obj = paginate(db, stmt, page=page, per_page=per_page)

    template = (
        "_partials/broken_rows.html"
        if request.headers.get("HX-Request")
        else "broken.html"
    )
    return templates.TemplateResponse(
        template,
        {
            "request": request,
            "page": page_obj,
            "endpoint": "/broken-backlinks",
        },
    )
