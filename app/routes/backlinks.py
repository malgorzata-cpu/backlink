from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.models import ActiveBacklink
from app.services.link_checker import check_many, check_one
from app.services.pagination import paginate
from app.templating import templates

router = APIRouter()

VALID_STATUSES = {"all", "pending", "ok", "missing", "error", "redirect"}


@router.get("/backlinks", response_class=HTMLResponse)
def list_backlinks(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    status: str = Query("all"),
    db: Session = Depends(get_db),
):
    if status not in VALID_STATUSES:
        status = "all"

    stmt = select(ActiveBacklink)
    if status != "all":
        stmt = stmt.where(ActiveBacklink.check_status == status)
    stmt = stmt.order_by(
        ActiveBacklink.domain_traffic.desc().nullslast(),
        ActiveBacklink.id.asc(),
    )
    page_obj = paginate(db, stmt, page=page, per_page=per_page)

    counts = dict(
        db.execute(
            select(ActiveBacklink.check_status, func.count())
            .group_by(ActiveBacklink.check_status)
        ).all()
    )

    template = (
        "_partials/backlinks_rows.html"
        if request.headers.get("HX-Request")
        else "backlinks.html"
    )
    return templates.TemplateResponse(
        template,
        {
            "request": request,
            "page": page_obj,
            "endpoint": "/backlinks",
            "status": status,
            "counts": counts,
        },
    )


@router.post("/backlinks/{backlink_id}/check", response_class=HTMLResponse)
def check_single(
    backlink_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    record = check_one(db, backlink_id)
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "_partials/backlinks_row.html",
            {"request": request, "row": record, "loop_index": record.id},
        )
    return RedirectResponse(url="/backlinks", status_code=303)


@router.post("/backlinks/check-batch")
def check_batch(
    background: BackgroundTasks,
    only_pending: bool = Query(True),
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    stmt = select(ActiveBacklink.id)
    if only_pending:
        stmt = stmt.where(ActiveBacklink.check_status == "pending")
    stmt = stmt.order_by(ActiveBacklink.id.asc()).limit(limit)
    ids = [row[0] for row in db.execute(stmt).all()]

    if ids:
        background.add_task(_run_batch_in_background, ids)
    return RedirectResponse(
        url=f"/backlinks?queued={len(ids)}",
        status_code=303,
    )


def _run_batch_in_background(ids: list[int]) -> None:
    """Runs in a worker thread; opens its own DB session."""
    db = SessionLocal()
    try:
        check_many(db, ids)
    finally:
        db.close()
