from datetime import date

from pydantic import BaseModel, Field


class MeasurementCreate(BaseModel):
    """Значение показателя на входе (импорт/форма).

    Показатель указывается по ``marker_code`` (см. справочник marker). Для
    количественных заполняется ``value_num``, для качественных — ``value_text``.
    """

    marker_code: str
    value_num: float | None = None
    value_text: str | None = None
    unit: str | None = None
    ref_low: float | None = None
    ref_high: float | None = None
    flag: str | None = None  # normal | high | low | positive | negative


class Measurement(BaseModel):
    """Значение показателя в выдаче (с подтянутым именем показателя)."""

    id: int
    marker_code: str | None = None
    marker_name: str | None = None
    value_num: float | None = None
    value_text: str | None = None
    unit: str | None = None
    ref_low: float | None = None
    ref_high: float | None = None
    flag: str | None = None


class AnalysisCreate(BaseModel):
    """Анализ (документ) на входе вместе со своими измерениями."""

    date: date
    title: str = Field(min_length=1)
    category: str | None = None
    lab: str | None = None
    source: str = "manual"
    source_ref: str | None = None
    document_path: str | None = None
    notes: str | None = None
    measurements: list[MeasurementCreate] = Field(default_factory=list)


class Analysis(BaseModel):
    """Анализ в выдаче вместе с измерениями."""

    id: int
    person_id: int
    date: date
    title: str
    category: str | None = None
    lab: str | None = None
    source: str
    source_ref: str | None = None
    document_path: str | None = None
    notes: str | None = None
    measurements: list[Measurement] = Field(default_factory=list)
