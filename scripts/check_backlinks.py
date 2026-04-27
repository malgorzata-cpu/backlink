"""Periodic CLI runner for backlink monitoring.

Usage:
    python -m scripts.check_backlinks                # checks all 'pending' rows (limit 500)
    python -m scripts.check_backlinks --all          # re-checks every row
    python -m scripts.check_backlinks --limit 100    # cap batch size
    python -m scripts.check_backlinks --concurrency 4

Schedule via Windows Task Scheduler / cron (e.g. daily) to keep statuses fresh.
"""

from __future__ import annotations

import argparse
from sqlalchemy import select

from app.db import SessionLocal
from app.models import ActiveBacklink
from app.services.link_checker import DEFAULT_CONCURRENCY, check_many


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="recheck every row, not only pending")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stmt = select(ActiveBacklink.id)
        if not args.all:
            stmt = stmt.where(ActiveBacklink.check_status == "pending")
        stmt = stmt.order_by(ActiveBacklink.id.asc()).limit(args.limit)
        ids = [r[0] for r in db.execute(stmt).all()]
        if not ids:
            print("Nothing to check.")
            return
        print(f"Checking {len(ids)} backlinks (concurrency={args.concurrency})...")
        done = check_many(db, ids, concurrency=args.concurrency)
        print(f"Done: {done} processed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
