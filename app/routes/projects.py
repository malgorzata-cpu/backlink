import re
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    ActiveBacklink,
    BrokenBacklink,
    ImportRun,
    LinkOpportunity,
    Project,
)
from app.templating import templates

router = APIRouter()

SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    s = SLUG_RE.sub("-", value.lower()).strip("-")
    return s or "project"


def _normalize_domain(value: str) -> str:
    v = value.strip().lower()
    for prefix in ("https://", "http://"):
        if v.startswith(prefix):
            v = v[len(prefix):]
    if v.startswith("www."):
        v = v[4:]
    return v.rstrip("/")


def _render_projects_list(request: Request, db: Session):
    projects = db.execute(select(Project).order_by(Project.name)).scalars().all()
    counts: dict[int, dict[str, int]] = {}
    for p in projects:
        counts[p.id] = {
            "opportunities": db.scalar(
                select(func.count())
                .select_from(LinkOpportunity)
                .where(LinkOpportunity.project_id == p.id)
            ) or 0,
            "broken": db.scalar(
                select(func.count())
                .select_from(BrokenBacklink)
                .where(BrokenBacklink.project_id == p.id)
            ) or 0,
            "active": db.scalar(
                select(func.count())
                .select_from(ActiveBacklink)
                .where(ActiveBacklink.project_id == p.id)
            ) or 0,
        }
    return templates.TemplateResponse(
        "projects.html",
        {"request": request, "projects": projects, "counts": counts},
    )


@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    return _render_projects_list(request, db)


@router.get("/projects", response_class=HTMLResponse)
def list_projects(request: Request, db: Session = Depends(get_db)):
    return _render_projects_list(request, db)


@router.get("/projects/new", response_class=HTMLResponse)
def new_project_form(request: Request):
    return templates.TemplateResponse(
        "project_form.html",
        {"request": request, "project": None, "error": None, "form": None},
    )


@router.post("/projects/new")
def create_project(
    request: Request,
    name: str = Form(...),
    primary_domain: str = Form(...),
    competitor_domain: str = Form(...),
    notes: Optional[str] = Form(""),
    db: Session = Depends(get_db),
):
    name_clean = name.strip()
    primary_clean = _normalize_domain(primary_domain)
    competitor_clean = _normalize_domain(competitor_domain)

    if not name_clean or not primary_clean or not competitor_clean:
        return templates.TemplateResponse(
            "project_form.html",
            {
                "request": request,
                "project": None,
                "error": "Wszystkie pola (nazwa, domena główna, konkurent) są wymagane.",
                "form": {
                    "name": name_clean,
                    "primary_domain": primary_clean,
                    "competitor_domain": competitor_clean,
                    "notes": notes or "",
                },
            },
            status_code=400,
        )

    base_slug = _slugify(name_clean)
    slug = base_slug
    n = 1
    while db.execute(select(Project).where(Project.slug == slug)).scalar_one_or_none():
        n += 1
        slug = f"{base_slug}-{n}"

    project = Project(
        slug=slug,
        name=name_clean,
        primary_domain=primary_clean,
        competitor_domain=competitor_clean,
        notes=(notes or "").strip() or None,
    )
    db.add(project)
    db.commit()

    response = RedirectResponse(url="/projects", status_code=303)
    response.set_cookie(
        "current_project_slug", slug, max_age=60 * 60 * 24 * 365, samesite="lax"
    )
    return response


@router.get("/projects/{slug}", response_class=HTMLResponse)
def edit_project_form(slug: str, request: Request, db: Session = Depends(get_db)):
    project = db.execute(
        select(Project).where(Project.slug == slug)
    ).scalar_one_or_none()
    if project is None:
        return RedirectResponse(url="/projects", status_code=303)
    return templates.TemplateResponse(
        "project_form.html",
        {"request": request, "project": project, "error": None, "form": None},
    )


@router.post("/projects/{slug}")
def update_project(
    slug: str,
    request: Request,
    name: str = Form(...),
    primary_domain: str = Form(...),
    competitor_domain: str = Form(...),
    notes: Optional[str] = Form(""),
    db: Session = Depends(get_db),
):
    project = db.execute(
        select(Project).where(Project.slug == slug)
    ).scalar_one_or_none()
    if project is None:
        return RedirectResponse(url="/projects", status_code=303)

    name_clean = name.strip()
    primary_clean = _normalize_domain(primary_domain)
    competitor_clean = _normalize_domain(competitor_domain)

    if not name_clean or not primary_clean or not competitor_clean:
        return templates.TemplateResponse(
            "project_form.html",
            {
                "request": request,
                "project": project,
                "error": "Wszystkie pola są wymagane.",
                "form": {
                    "name": name_clean,
                    "primary_domain": primary_clean,
                    "competitor_domain": competitor_clean,
                    "notes": notes or "",
                },
            },
            status_code=400,
        )

    project.name = name_clean
    project.primary_domain = primary_clean
    project.competitor_domain = competitor_clean
    project.notes = (notes or "").strip() or None
    db.commit()
    return RedirectResponse(url="/projects", status_code=303)


@router.post("/projects/{slug}/delete")
def delete_project(slug: str, db: Session = Depends(get_db)):
    project = db.execute(
        select(Project).where(Project.slug == slug)
    ).scalar_one_or_none()
    if project is None:
        return RedirectResponse(url="/projects", status_code=303)

    # Cascade-delete project's data manually (no DB-level cascade configured).
    db.execute(
        LinkOpportunity.__table__.delete().where(
            LinkOpportunity.project_id == project.id
        )
    )
    db.execute(
        BrokenBacklink.__table__.delete().where(
            BrokenBacklink.project_id == project.id
        )
    )
    db.execute(
        ActiveBacklink.__table__.delete().where(
            ActiveBacklink.project_id == project.id
        )
    )
    db.execute(
        ImportRun.__table__.delete().where(ImportRun.project_id == project.id)
    )
    db.delete(project)
    db.commit()

    response = RedirectResponse(url="/projects", status_code=303)
    response.delete_cookie("current_project_slug")
    return response


@router.post("/projects/{slug}/select")
def select_project(slug: str, db: Session = Depends(get_db)):
    project = db.execute(
        select(Project).where(Project.slug == slug)
    ).scalar_one_or_none()
    response = RedirectResponse(url="/dashboard", status_code=303)
    if project:
        response.set_cookie(
            "current_project_slug",
            slug,
            max_age=60 * 60 * 24 * 365,
            samesite="lax",
        )
    return response
