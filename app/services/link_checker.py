"""Backlink monitor: fetches each referring page and checks whether it still
contains an <a> link pointing to our project's primary domain.

Two booleans are reported per check:
- link_found: any <a href> resolves to host containing the project's primary_domain
- exact_target_match: at least one such href, after normalization, equals target_url
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActiveBacklink, Project


logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; LinkBuildingMonitor/0.2; "
    "+https://github.com/malgorzata-cpu/backlink) Python/httpx"
)
TIMEOUT_SECONDS = 15.0
MAX_HTML_BYTES = 5 * 1024 * 1024  # cap per-page download to 5 MiB
DEFAULT_CONCURRENCY = 8


@dataclass
class CheckResult:
    check_status: str  # ok | missing | error | redirect
    http_status: int | None
    link_found: bool
    exact_target_match: bool
    found_count: int
    found_anchor: str | None
    found_hrefs: str | None  # up to 3, "|"-separated
    error_message: str | None


def _normalize_url(url: str) -> str:
    """Lowercase host, strip 'www.', drop fragment, normalize trailing slash."""
    if not url:
        return ""
    try:
        p = urlparse(url.strip())
    except ValueError:
        return url.strip()
    host = (p.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = p.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return urlunparse((p.scheme.lower() or "https", host, path, "", p.query, ""))


def _normalize_host(host: str) -> str:
    h = host.lower().strip()
    if h.startswith("www."):
        h = h[4:]
    return h


def _host_matches(href_host: str, our_host: str) -> bool:
    h = _normalize_host(href_host)
    our = _normalize_host(our_host)
    return h == our or h.endswith("." + our)


def _scan_html(
    html: str, base_url: str, target_url: str | None, our_host: str
) -> tuple[int, list[str], str | None, bool]:
    """Return (count, sample_hrefs, first_anchor, exact_match)."""
    soup = BeautifulSoup(html, "html.parser")
    target_norm = _normalize_url(target_url) if target_url else ""
    count = 0
    sample: list[str] = []
    first_anchor: str | None = None
    exact_match = False

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        absolute = urljoin(base_url, href)
        try:
            host = urlparse(absolute).netloc
        except ValueError:
            continue
        if not host or not _host_matches(host, our_host):
            continue
        count += 1
        if len(sample) < 3:
            sample.append(absolute)
        if first_anchor is None:
            anchor_text = a.get_text(strip=True) or "[brak]"
            first_anchor = anchor_text[:200]
        if target_norm and _normalize_url(absolute) == target_norm:
            exact_match = True
    return count, sample, first_anchor, exact_match


def check_backlink(
    referring_page_url: str,
    target_url: str | None,
    our_host: str,
    *,
    client: httpx.Client | None = None,
) -> CheckResult:
    own_client = client is None
    if own_client:
        client = httpx.Client(
            timeout=TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "pl,en;q=0.7"},
        )

    try:
        try:
            resp = client.get(referring_page_url)
        except httpx.RequestError as e:
            return CheckResult(
                check_status="error",
                http_status=None,
                link_found=False,
                exact_target_match=False,
                found_count=0,
                found_anchor=None,
                found_hrefs=None,
                error_message=f"{type(e).__name__}: {str(e)[:300]}",
            )

        http_status = resp.status_code
        if http_status >= 400:
            return CheckResult(
                check_status="error",
                http_status=http_status,
                link_found=False,
                exact_target_match=False,
                found_count=0,
                found_anchor=None,
                found_hrefs=None,
                error_message=f"HTTP {http_status}",
            )

        # Detect redirect away from the original referring URL host.
        final_host = _normalize_host(urlparse(str(resp.url)).netloc)
        original_host = _normalize_host(urlparse(referring_page_url).netloc)
        redirected_offsite = bool(final_host) and bool(original_host) and final_host != original_host

        ctype = resp.headers.get("content-type", "").lower()
        if "html" not in ctype and "xml" not in ctype:
            return CheckResult(
                check_status="error",
                http_status=http_status,
                link_found=False,
                exact_target_match=False,
                found_count=0,
                found_anchor=None,
                found_hrefs=None,
                error_message=f"Non-HTML content-type: {ctype[:120]}",
            )

        html = resp.text[:MAX_HTML_BYTES]
        count, sample, anchor, exact = _scan_html(html, str(resp.url), target_url, our_host)

        if count > 0:
            status = "ok"
        elif redirected_offsite:
            status = "redirect"
        else:
            status = "missing"

        return CheckResult(
            check_status=status,
            http_status=http_status,
            link_found=count > 0,
            exact_target_match=exact,
            found_count=count,
            found_anchor=anchor,
            found_hrefs="|".join(sample) if sample else None,
            error_message=None,
        )
    finally:
        if own_client:
            client.close()


def check_one(db: Session, backlink_id: int) -> ActiveBacklink:
    record = db.get(ActiveBacklink, backlink_id)
    if record is None:
        raise ValueError(f"ActiveBacklink id={backlink_id} not found")
    project = db.get(Project, record.project_id)
    if project is None:
        raise ValueError(f"Project id={record.project_id} not found")
    result = check_backlink(record.referring_page_url, record.target_url, project.primary_domain)
    _apply_result(record, result)
    db.commit()
    db.refresh(record)
    return record


def check_many(
    db: Session,
    backlink_ids: Iterable[int],
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> int:
    """Check the given records concurrently; returns the number processed."""
    ids = list(backlink_ids)
    if not ids:
        return 0

    records = (
        db.query(ActiveBacklink).filter(ActiveBacklink.id.in_(ids)).all()
    )
    by_id = {r.id: r for r in records}

    project_ids = {r.project_id for r in records}
    projects_rows = db.execute(
        select(Project).where(Project.id.in_(project_ids))
    ).scalars().all()
    project_host_by_id = {p.id: p.primary_domain for p in projects_rows}

    with httpx.Client(
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "pl,en;q=0.7"},
    ) as client:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            future_to_id = {
                pool.submit(
                    check_backlink,
                    rec.referring_page_url,
                    rec.target_url,
                    project_host_by_id[rec.project_id],
                    client=client,
                ): rec.id
                for rec in records
            }
            done = 0
            for fut in as_completed(future_to_id):
                rid = future_to_id[fut]
                rec = by_id[rid]
                try:
                    result = fut.result()
                except Exception as e:
                    result = CheckResult(
                        check_status="error",
                        http_status=None,
                        link_found=False,
                        exact_target_match=False,
                        found_count=0,
                        found_anchor=None,
                        found_hrefs=None,
                        error_message=f"{type(e).__name__}: {str(e)[:300]}",
                    )
                _apply_result(rec, result)
                done += 1
                if done % 20 == 0:
                    db.commit()
        db.commit()
    return done


def _apply_result(record: ActiveBacklink, result: CheckResult) -> None:
    record.check_status = result.check_status
    record.last_checked_at = datetime.utcnow()
    record.http_status = result.http_status
    record.link_found = result.link_found
    record.exact_target_match = result.exact_target_match
    record.found_count = result.found_count
    record.found_anchor = result.found_anchor
    record.found_hrefs = result.found_hrefs
    record.error_message = result.error_message
