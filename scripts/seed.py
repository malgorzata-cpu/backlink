"""Idempotent seed: imports the two known Ahrefs CSV files from data/.

Skips a file if an ImportRun with status='success' already exists for that filename.
"""

from pathlib import Path

from sqlalchemy import select

from app.config import PROJECT_ROOT
from app.db import SessionLocal, engine
from app.models import Base, ImportRun
from app.services.csv_import import (
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
]


def main() -> None:
    Base.metadata.create_all(engine)

    data_dir = PROJECT_ROOT / "data"
    db = SessionLocal()
    try:
        for filename, source_type in KNOWN_FILES:
            path = data_dir / filename
            if not path.exists():
                print(f"[skip] {filename} — file not found in data/")
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
            run = import_file(db, path, source_type)
            print(f"  -> run #{run.id}: {run.row_count} rows ({run.status})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
