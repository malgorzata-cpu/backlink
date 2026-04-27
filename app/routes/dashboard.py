from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ActiveBacklink, BrokenBacklink, ImportRun, LinkOpportunity
from app.templating import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    opportunities_count = db.scalar(select(func.count()).select_from(LinkOpportunity)) or 0
    broken_count = db.scalar(select(func.count()).select_from(BrokenBacklink)) or 0
    active_count = db.scalar(select(func.count()).select_from(ActiveBacklink)) or 0
    active_status_counts = dict(
        db.execute(
            select(ActiveBacklink.check_status, func.count())
            .group_by(ActiveBacklink.check_status)
        ).all()
    )

    last_imports = (
        db.execute(
            select(ImportRun)
            .order_by(ImportRun.started_at.desc())
            .limit(10)
        )
        .scalars()
        .all()
    )

    last_opp_import = (
        db.execute(
            select(ImportRun)
            .where(ImportRun.source_type == "link_intersect", ImportRun.status == "success")
            .order_by(ImportRun.finished_at.desc())
            .limit(1)
        )
        .scalar_one_or_none()
    )
    last_broken_import = (
        db.execute(
            select(ImportRun)
            .where(ImportRun.source_type == "broken_backlinks", ImportRun.status == "success")
            .order_by(ImportRun.finished_at.desc())
            .limit(1)
        )
        .scalar_one_or_none()
    )
    last_active_import = (
        db.execute(
            select(ImportRun)
            .where(ImportRun.source_type == "active_backlinks", ImportRun.status == "success")
            .order_by(ImportRun.finished_at.desc())
            .limit(1)
        )
        .scalar_one_or_none()
    )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "opportunities_count": opportunities_count,
            "broken_count": broken_count,
            "active_count": active_count,
            "active_status_counts": active_status_counts,
            "last_opp_import": last_opp_import,
            "last_broken_import": last_broken_import,
            "last_active_import": last_active_import,
            "last_imports": last_imports,
        },
    )
