from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import LinkOpportunity
from app.services.pagination import paginate
from app.templating import templates

router = APIRouter()


@router.get("/opportunities", response_class=HTMLResponse)
def list_opportunities(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    current = getattr(request.state, "current_project", None)
    if current is None:
        return RedirectResponse(url="/projects/new", status_code=303)

    stmt = (
        select(LinkOpportunity)
        .where(LinkOpportunity.project_id == current.id)
        .order_by(
            LinkOpportunity.domain_traffic.desc().nullslast(),
            LinkOpportunity.domain_rating.desc().nullslast(),
            LinkOpportunity.page_traffic.desc().nullslast(),
            LinkOpportunity.id.asc(),
        )
    )
    page_obj = paginate(db, stmt, page=page, per_page=per_page)

    template = (
        "_partials/opportunities_rows.html"
        if request.headers.get("HX-Request")
        else "opportunities.html"
    )
    return templates.TemplateResponse(
        template,
        {
            "request": request,
            "page": page_obj,
            "endpoint": "/opportunities",
        },
    )
