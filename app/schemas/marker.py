from pydantic import BaseModel


class Marker(BaseModel):
    """Показатель из справочника."""

    id: int
    code: str
    name: str
    unit: str | None = None
    ref_low: float | None = None
    ref_high: float | None = None
