from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class TimelineEvent(BaseModel):
    """Единица единой ленты событий по человеку.

    Сводит разнородные сущности (анализы, визиты, болезни, рекомендации) к
    общему виду для сортировки по дате и отрисовки в хронологии.
    """

    date: date
    kind: str  # analysis | visit | illness | recommendation
    title: str
    detail: str | None = None
    ref_id: int | None = None  # id исходной записи
    extra: dict[str, Any] = Field(default_factory=dict)
