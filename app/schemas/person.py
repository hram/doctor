from datetime import date, datetime

from pydantic import BaseModel, Field


class PersonCreate(BaseModel):
    """Данные для создания/обновления человека (вход API, формы, импорт)."""

    name: str = Field(min_length=1, max_length=100)
    full_name: str | None = None
    birth_date: date | None = None
    role: str = "child"  # parent | child
    sex: str | None = None
    notes: str | None = None


class Person(BaseModel):
    """Человек в том виде, в котором отдаётся наружу."""

    id: int
    name: str
    full_name: str | None = None
    birth_date: date | None = None
    role: str
    sex: str | None = None
    notes: str | None = None
    created_at: datetime
