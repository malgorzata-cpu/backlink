"""CSV import for Ahrefs exports (UTF-16 LE, TAB-delimited, quoted fields)."""

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.models import ActiveBacklink, BrokenBacklink, ImportRun, LinkOpportunity


SOURCE_LINK_INTERSECT = "link_intersect"
SOURCE_BROKEN_BACKLINKS = "broken_backlinks"
SOURCE_ACTIVE_BACKLINKS = "active_backlinks"

BATCH_SIZE = 1000


# Each value is either a string (target attribute, value kept as string)
# or a tuple (target_attribute, type) where type ∈ {int, bool, datetime}.
LINK_INTERSECT_MAP: dict[str, Any] = {
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
    "rafa-wino.pl/": "target_rafa",
    "winnicalidla.pl/": "target_winnicalidla",
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

SOURCE_REGISTRY = {
    SOURCE_LINK_INTERSECT: (LinkOpportunity, LINK_INTERSECT_MAP),
    SOURCE_BROKEN_BACKLINKS: (BrokenBacklink, BROKEN_BACKLINKS_MAP),
    SOURCE_ACTIVE_BACKLINKS: (ActiveBacklink, ACTIVE_BACKLINKS_MAP),
}


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


def import_file(db: Session, path: Path, source_type: str) -> ImportRun:
    if source_type not in SOURCE_REGISTRY:
        raise ValueError(f"Unknown source_type: {source_type!r}")

    Model, col_map = SOURCE_REGISTRY[source_type]

    run = ImportRun(
        source_type=source_type,
        filename=path.name,
        status="running",
    )
    db.add(run)
    db.flush()  # populate run.id

    count = 0
    try:
        batch: list[dict] = []
        for row in iter_rows(path, col_map):
            batch.append({**row, "import_run_id": run.id})
            if len(batch) >= BATCH_SIZE:
                db.execute(Model.__table__.insert(), batch)
                count += len(batch)
                batch = []
        if batch:
            db.execute(Model.__table__.insert(), batch)
            count += len(batch)
        run.row_count = count
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
