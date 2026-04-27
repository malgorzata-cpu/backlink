"""CSV import for Ahrefs exports (UTF-16 LE, TAB-delimited, quoted fields).

Per-project import with deduplication.

Natural keys (per source_type):
- link_intersect:    (project_id, referring_page_url)
- broken_backlinks:  (project_id, referring_page_url, target_url)
- active_backlinks:  (project_id, referring_page_url, target_url)
- + optional anchor when dedup_with_anchor=True (only meaningful for backlinks)

On re-upload, rows matching the natural key are UPDATEd (Ahrefs metrics refreshed),
new rows are INSERTed. For active_backlinks, monitoring fields populated by
link_checker (check_status, last_checked_at, ...) are NEVER touched on update —
re-importing a fresh export does not wipe check history.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import (
    ActiveBacklink,
    BrokenBacklink,
    ImportRun,
    LinkOpportunity,
    Project,
)


SOURCE_LINK_INTERSECT = "link_intersect"
SOURCE_BROKEN_BACKLINKS = "broken_backlinks"
SOURCE_ACTIVE_BACKLINKS = "active_backlinks"

BATCH_SIZE = 1000


# Static base map for link_intersect — the two domain target columns are added
# dynamically per-project in _build_link_intersect_map.
LINK_INTERSECT_BASE_MAP: dict[str, Any] = {
    "Referring page title": "referring_page_title",
    "Referring page URL": "referring_page_url",
    "Language": "language",
    "Platform": "platform",
    "Type": "type",
    "Author": "author",
    "Redirect Code": ("redirect_code", int),
    "Domain rating": ("domain_rating", int),
    "UR": ("url_rating", int),
    "Domain traffic": ("domain_traffic", int),
    "Referring domains": ("referring_domains", int),
    "Page traffic": ("page_traffic", int),
    "Intersect": ("intersect", int),
}

BROKEN_BACKLINKS_MAP: dict[str, Any] = {
    "Referring page title": "referring_page_title",
    "Referring page URL": "referring_page_url",
    "Language": "language",
    "Platform": "platform",
    "Referring page HTTP code": ("referring_page_http_code", int),
    "Domain rating": ("domain_rating", int),
    "UR": ("url_rating", int),
    "Domain traffic": ("domain_traffic", int),
    "Referring domains": ("referring_domains", int),
    "Linked domains": ("linked_domains", int),
    "External links": ("external_links", int),
    "Page traffic": ("page_traffic", int),
    "Keywords": ("keywords", int),
    "Target URL": "target_url",
    "Target page HTTP code": ("target_page_http_code", int),
    "Left context": "left_context",
    "Anchor": "anchor",
    "Right context": "right_context",
    "Redirect Chain URLs": "redirect_chain_urls",
    "Redirect Chain status codes": "redirect_chain_status_codes",
    "Type": "type",
    "Is spam": ("is_spam", bool),
    "Content": ("content", bool),
    "Nofollow": ("nofollow", bool),
    "UGC": ("ugc", bool),
    "Sponsored": ("sponsored", bool),
    "Rendered": ("rendered", bool),
    "Raw": ("raw", bool),
    "Target checked": ("target_checked", datetime),
    "Ref. page checked": ("ref_page_checked", datetime),
    "Author": "author",
    "Page type": "page_type",
    "Page category": "page_category",
}

ACTIVE_BACKLINKS_MAP: dict[str, Any] = {
    "Referring page title": "referring_page_title",
    "Referring page URL": "referring_page_url",
    "Language": "language",
    "Platform": "platform",
    "Referring page HTTP code": ("referring_page_http_code", int),
    "Domain rating": ("domain_rating", int),
    "UR": ("url_rating", int),
    "Domain traffic": ("domain_traffic", int),
    "Referring domains": ("referring_domains", int),
    "Linked domains": ("linked_domains", int),
    "External links": ("external_links", int),
    "Page traffic": ("page_traffic", int),
    "Keywords": ("keywords", int),
    "Target URL": "target_url",
    "Left context": "left_context",
    "Anchor": "anchor",
    "Right context": "right_context",
    "Redirect Chain URLs": "redirect_chain_urls",
    "Redirect Chain status codes": "redirect_chain_status_codes",
    "Type": "type",
    "Is spam": ("is_spam", bool),
    "Content": ("content", bool),
    "Nofollow": ("nofollow", bool),
    "UGC": ("ugc", bool),
    "Sponsored": ("sponsored", bool),
    "Rendered": ("rendered", bool),
    "Raw": ("raw", bool),
    "Lost status": "lost_status",
    "Drop reason": "drop_reason",
    "Discovered status": "discovered_status",
    "First seen": ("first_seen", datetime),
    "Last seen": ("last_seen", datetime),
    "Lost": ("lost", datetime),
    "Author": "author",
    "Page type": "page_type",
    "Page category": "page_category",
    "Links in group": ("links_in_group", int),
}


def _build_link_intersect_map(project: Project) -> dict[str, Any]:
    m: dict[str, Any] = dict(LINK_INTERSECT_BASE_MAP)
    m[f"{project.primary_domain}/"] = "target_primary"
    m[f"{project.competitor_domain}/"] = "target_competitor"
    return m


SOURCE_REGISTRY: dict[str, type] = {
    SOURCE_LINK_INTERSECT: LinkOpportunity,
    SOURCE_BROKEN_BACKLINKS: BrokenBacklink,
    SOURCE_ACTIVE_BACKLINKS: ActiveBacklink,
}

# Set when source_type is on the upload form. Always corresponds to a Model.
SOURCE_TYPES = list(SOURCE_REGISTRY.keys())


def _coerce(value: str | None, typ: type = str):
    if value is None:
        return None
    value = value.strip()
    if value == "":
        return None
    if typ is int:
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None
    if typ is bool:
        return value.lower() in {"true", "1", "yes"}
    if typ is datetime:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None
    return value


def _open_ahrefs_csv(path: Path):
    """Ahrefs exports UTF-16 LE with BOM. encoding='utf-16' auto-strips the BOM."""
    return open(path, "r", encoding="utf-16", newline="")


def _build_column_map(source_type: str, project: Project) -> dict[str, Any]:
    if source_type == SOURCE_LINK_INTERSECT:
        return _build_link_intersect_map(project)
    if source_type == SOURCE_BROKEN_BACKLINKS:
        return dict(BROKEN_BACKLINKS_MAP)
    if source_type == SOURCE_ACTIVE_BACKLINKS:
        return dict(ACTIVE_BACKLINKS_MAP)
    raise ValueError(f"Unknown source_type: {source_type!r}")


def _natural_key_columns(source_type: str, dedup_with_anchor: bool) -> list[str]:
    cols = ["referring_page_url"]
    if source_type in (SOURCE_BROKEN_BACKLINKS, SOURCE_ACTIVE_BACKLINKS):
        cols.append("target_url")
        if dedup_with_anchor:
            cols.append("anchor")
    return cols


def iter_rows(path: Path, column_map: dict) -> Iterable[dict]:
    with _open_ahrefs_csv(path) as f:
        reader = csv.DictReader(f, delimiter="\t", quotechar='"')
        for raw in reader:
            out: dict[str, Any] = {}
            for header, target in column_map.items():
                cell = raw.get(header)
                if isinstance(target, tuple):
                    attr, typ = target
                    out[attr] = _coerce(cell, typ)
                else:
                    out[target] = _coerce(cell, str)
            yield out


def _validate_link_intersect_headers(path: Path, project: Project) -> None:
    with _open_ahrefs_csv(path) as f:
        reader = csv.reader(f, delimiter="\t", quotechar='"')
        headers = next(reader, [])
    expected = (f"{project.primary_domain}/", f"{project.competitor_domain}/")
    missing = [h for h in expected if h not in headers]
    if missing:
        raise ValueError(
            f"link_intersect CSV is missing target columns for this project: {missing}. "
            f"Project domains: primary={project.primary_domain!r}, "
            f"competitor={project.competitor_domain!r}. "
            f"Available headers: {headers}"
        )


def import_file(
    db: Session,
    path: Path,
    source_type: str,
    project_id: int,
    *,
    dedup_with_anchor: bool = False,
) -> ImportRun:
    if source_type not in SOURCE_REGISTRY:
        raise ValueError(f"Unknown source_type: {source_type!r}")

    project = db.get(Project, project_id)
    if project is None:
        raise ValueError(f"Project id={project_id} not found")

    Model = SOURCE_REGISTRY[source_type]
    col_map = _build_column_map(source_type, project)
    key_cols = _natural_key_columns(source_type, dedup_with_anchor)

    if source_type == SOURCE_LINK_INTERSECT:
        _validate_link_intersect_headers(path, project)

    # Pre-load existing rows' natural keys for this project → id
    select_cols = [getattr(Model, c) for c in key_cols] + [Model.id]
    existing = db.execute(
        select(*select_cols).where(Model.project_id == project_id)
    ).all()
    existing_by_key: dict[tuple, int] = {
        tuple(row[i] for i in range(len(key_cols))): row[-1] for row in existing
    }

    run = ImportRun(
        project_id=project_id,
        source_type=source_type,
        filename=path.name,
        status="running",
        dedup_with_anchor=dedup_with_anchor,
    )
    db.add(run)
    db.flush()  # populate run.id

    inserted = 0
    updated = 0
    try:
        insert_batch: list[dict] = []
        update_batch: list[dict] = []

        for row in iter_rows(path, col_map):
            row["project_id"] = project_id
            row["import_run_id"] = run.id
            key = tuple(row.get(c) for c in key_cols)
            existing_id = existing_by_key.get(key)

            if existing_id is not None:
                # Update existing row. Note: monitoring fields (check_status,
                # last_checked_at, ...) are not in any column_map, so they're
                # absent from `row` and naturally preserved. created_at is also
                # not in column_map.
                update_row = dict(row)
                update_row["id"] = existing_id
                update_batch.append(update_row)
            else:
                insert_batch.append(row)

            if len(insert_batch) >= BATCH_SIZE:
                db.execute(Model.__table__.insert(), insert_batch)
                inserted += len(insert_batch)
                insert_batch = []
            if len(update_batch) >= BATCH_SIZE:
                db.execute(update(Model), update_batch)
                updated += len(update_batch)
                update_batch = []

        if insert_batch:
            db.execute(Model.__table__.insert(), insert_batch)
            inserted += len(insert_batch)
        if update_batch:
            db.execute(update(Model), update_batch)
            updated += len(update_batch)

        run.row_count = inserted + updated
        run.rows_inserted = inserted
        run.rows_updated = updated
        run.status = "success"
    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)[:2000]
        run.finished_at = datetime.utcnow()
        db.commit()
        raise
    finally:
        if run.status != "failed":
            run.finished_at = datetime.utcnow()
            db.commit()
    return run
