from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _format_int(value):
    if value is None:
        return "—"
    try:
        return f"{int(value):,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(value)


def _truncate(value, length: int = 80):
    if value is None:
        return ""
    s = str(value)
    return s if len(s) <= length else s[: length - 1] + "…"


templates.env.filters["fmt_int"] = _format_int
templates.env.filters["truncate_chars"] = _truncate
