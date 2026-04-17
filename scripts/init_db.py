"""Bootstrap initial DB schema using SQLAlchemy create_all.

Use this for first-time local setup. For production schema evolution,
use Alembic: `alembic revision --autogenerate -m "..."` and `alembic upgrade head`.
"""

from app.config import settings
from app.db import engine
from app.models import Base


def main() -> None:
    print(f"Creating schema at {settings.database_url}")
    Base.metadata.create_all(engine)
    print("Done. Tables created (or already existed).")


if __name__ == "__main__":
    main()
