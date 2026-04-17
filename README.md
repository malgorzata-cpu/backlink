# Link Building Dashboard

Dashboard do wykrywania okazji linkowych z eksportów Ahrefs (link intersect / broken backlinks).

## Quick start (lokalnie)

```bash
python -m venv .venv
source .venv/Scripts/activate     # Windows: source .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env

# Wrzuć pliki CSV Ahrefs do data/
# Następnie:
python -m scripts.seed
uvicorn app.main:app --reload
```

Otwórz <http://localhost:8000>.

## Widoki

- `/` — dashboard z liczbami i ostatnim importem
- `/opportunities` — link intersect, sort `Domain Traffic ↓, DR ↓, Page Traffic ↓`, paginacja 100/stronę
- `/broken-backlinks` — broken backlinki, sort `Domain Traffic ↓`
- `/upload` — wgraj nowy CSV (radio source_type)
- `/imports` — historia importów

## Stack

FastAPI + SQLAlchemy 2.x + Jinja2 + Bootstrap 5 + HTMX. SQLite lokalnie, PostgreSQL na produkcji (zmiana w `.env`).

## Deploy (Docker)

```bash
# Na serwerze
cp .env.example .env
# Edytuj .env — DATABASE_URL=postgresql+psycopg://..., POSTGRES_PASSWORD=...
docker compose up -d --build
docker compose exec app python -m scripts.seed   # opcjonalnie, jeśli pliki w ./data/
```

## Rozbudowa

Nowe źródło = (1) nowy model w `app/models/`, (2) wpis w `app/services/csv_import.py:SOURCE_REGISTRY` z column map, (3) nowy route w `app/routes/`, (4) szablon. Brak refactoru.
