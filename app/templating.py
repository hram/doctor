from datetime import date, datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.config import get_settings

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _datetimeformat(value: datetime | str, fmt: str = "%d.%m.%Y %H:%M") -> str:
    """Jinja-фильтр для дат-времени. Принимает datetime или ISO-строку из SQLite."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.strftime(fmt)


def _dateformat(value: date | str | None, fmt: str = "%d.%m.%Y") -> str:
    """Jinja-фильтр для дат. Принимает date или ISO-строку (YYYY-MM-DD)."""
    if value is None:
        return ""
    if isinstance(value, str):
        value = date.fromisoformat(value)
    return value.strftime(fmt)


templates.env.filters["datetimeformat"] = _datetimeformat
templates.env.filters["dateformat"] = _dateformat
templates.env.globals["app_name"] = get_settings().app_name
