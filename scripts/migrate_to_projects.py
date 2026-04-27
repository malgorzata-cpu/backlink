"""One-shot migration to multi-project schema.

Steps (idempotent — safe to run multiple times):
1. Create `projects` table (via Base.metadata.create_all).
2. Create default project 'rafa-wino-pl' if missing.
3. Add `project_id` column to existing tables (link_opportunities, broken_backlinks,
   active_backlinks, import_runs) and backfill with default project id.
4. Add new ImportRun columns (rows_inserted, rows_updated, dedup_with_anchor).
5. Rename link_opportunities columns: target_rafa -> target_primary,
   target_winnicalidla -> target_competitor.
6. Create dedup helper indexes.

Run: `python -m scripts.migrate_to_projects`
"""

from sqlalchemy import text

from app.db import SessionLocal, engine
from app.models import Base
import app.models  # noqa: F401  -- registers all models with metadata


def column_exists(db, table: str, column: str) -> bool:
    rows = db.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def index_exists(db, name: str) -> bool:
    row = db.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='index' AND name=:n"),
        {"n": name},
    ).fetchone()
    return row is not None


def main() -> None:
    # create_all is idempotent — adds projects table if missing, ignores existing.
    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        existing = db.execute(
            text("SELECT id FROM projects WHERE slug = 'rafa-wino-pl'")
        ).fetchone()
        if existing:
            project_id = existing[0]
            print(f"[skip] Default project already exists (id={project_id})")
        else:
            db.execute(
                text(
                    """
                    INSERT INTO projects
                        (slug, name, primary_domain, competitor_domain, notes,
                         created_at, updated_at)
                    VALUES
                        ('rafa-wino-pl', 'Rafa Wino', 'rafa-wino.pl', 'winnicalidla.pl',
                         'Domyślny projekt utworzony przy migracji do trybu multi-project',
                         CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """
                )
            )
            project_id = db.execute(
                text("SELECT id FROM projects WHERE slug = 'rafa-wino-pl'")
            ).fetchone()[0]
            print(f"[create] Default project (id={project_id})")

        # 1. Add project_id to existing data tables + backfill.
        for table in (
            "link_opportunities",
            "broken_backlinks",
            "active_backlinks",
            "import_runs",
        ):
            if not column_exists(db, table, "project_id"):
                db.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN project_id INTEGER")
                )
                print(f"[alter] Added project_id to {table}")
            updated = db.execute(
                text(
                    f"UPDATE {table} SET project_id = :pid WHERE project_id IS NULL"
                ),
                {"pid": project_id},
            )
            n = updated.rowcount if hasattr(updated, "rowcount") else "?"
            print(f"[backfill] {table}: {n} rows tagged with project_id={project_id}")

        # 2. Add new ImportRun columns.
        for col_def in (
            ("rows_inserted", "INTEGER"),
            ("rows_updated", "INTEGER"),
            ("dedup_with_anchor", "BOOLEAN"),
        ):
            col, typ = col_def
            if not column_exists(db, "import_runs", col):
                db.execute(text(f"ALTER TABLE import_runs ADD COLUMN {col} {typ}"))
                print(f"[alter] Added import_runs.{col}")

        # 3. Rename link_opportunities columns (SQLite >= 3.25 supports RENAME COLUMN).
        if column_exists(db, "link_opportunities", "target_rafa") and not column_exists(
            db, "link_opportunities", "target_primary"
        ):
            db.execute(
                text(
                    "ALTER TABLE link_opportunities RENAME COLUMN target_rafa TO target_primary"
                )
            )
            print("[rename] link_opportunities.target_rafa -> target_primary")
        if column_exists(
            db, "link_opportunities", "target_winnicalidla"
        ) and not column_exists(db, "link_opportunities", "target_competitor"):
            db.execute(
                text(
                    "ALTER TABLE link_opportunities RENAME COLUMN target_winnicalidla TO target_competitor"
                )
            )
            print(
                "[rename] link_opportunities.target_winnicalidla -> target_competitor"
            )

        # 4. Helper indexes for dedup lookup.
        for idx_name, idx_sql in (
            (
                "ix_lo_dedup",
                "CREATE INDEX ix_lo_dedup ON link_opportunities (project_id, referring_page_url)",
            ),
            (
                "ix_bb_dedup",
                "CREATE INDEX ix_bb_dedup ON broken_backlinks (project_id, referring_page_url, target_url)",
            ),
            (
                "ix_ab_dedup",
                "CREATE INDEX ix_ab_dedup ON active_backlinks (project_id, referring_page_url, target_url)",
            ),
        ):
            if not index_exists(db, idx_name):
                db.execute(text(idx_sql))
                print(f"[index] {idx_name}")

        db.commit()
        print("\nMigration complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
