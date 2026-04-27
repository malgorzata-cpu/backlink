"""Idempotent seed: imports the known Ahrefs CSV files for the default project.

Skips a file if an ImportRun with status='success' already exists for that filename.
Creates a default project ('rafa-wino-pl') if none exists.
"""

from pathlib import Path

from sqlalchemy import select

from app.config import PROJECT_ROOT
from app.db import SessionLocal, engine
from app.models import Base, ImportRun, Project
from app.services.csv_import import (
    SOURCE_ACTIVE_BACKLINKS,
    SOURCE_BROKEN_BACKLINKS,
    SOURCE_LINK_INTERSECT,
    import_file,
)


KNOWN_FILES = [
    (
        "rafa-wino.pl-link-intersect-refpages-subdoma_2026-04-17_09-35-11.csv",
        SOURCE_LINK_INTERSECT,
    ),
    (
        "winnicalidla.pl-broken-backlinks-subdomains_2026-04-17_09-34-06.csv",
        SOURCE_BROKEN_BACKLINKS,
    ),
    (
        "rafa-wino.pl-backlinks-subdomains_2026-04-17_08-18-41.csv",
        SOURCE_ACTIVE_BACKLINKS,
    ),
]


def main() -> None:
    Base.metadata.create_all(engine)

    data_dir = PROJECT_ROOT / "data"
    db = SessionLocal()
    try:
        project = db.execute(
            select(Project).where(Project.slug == "rafa-wino-pl")
        ).scalar_one_or_none()
        if project is None:
            project = Project(
                slug="rafa-wino-pl",
                name="Rafa Wino",
                primary_domain="rafa-wino.pl",
                competitor_domain="winnicalidla.pl",
                notes="Domyślny projekt seedowany ze skryptu",
            )
            db.add(project)
            db.commit()
            db.refresh(project)
            print(f"[create] Default project (id={project.id})")
        else:
            print(f"[skip] Default project exists (id={project.id})")

        for filename, source_type in KNOWN_FILES:
            # Look in data/ first (preferred), then project root as fallback.
            path = data_dir / filename
            if not path.exists():
                fallback = PROJECT_ROOT / filename
                if fallback.exists():
                    path = fallback
            if not path.exists():
                print(f"[skip] {filename} — file not found in data/ or project root")
                continue

            existing = db.execute(
                select(ImportRun).where(
                    ImportRun.filename == filename,
                    ImportRun.status == "success",
                )
            ).scalar_one_or_none()
            if existing:
                print(
                    f"[skip] {filename} — already imported "
                    f"(run #{existing.id}, {existing.row_count} rows)"
                )
                continue

            print(f"[import] {filename} as {source_type} ...")
            run = import_file(db, path, source_type, project.id)
            print(
                f"  -> run #{run.id}: {run.row_count} total "
                f"(insert={run.rows_inserted}, update={run.rows_updated})"
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
