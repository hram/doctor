from datetime import date

from pydantic import BaseModel, Field


class IllnessCreate(BaseModel):
    """Эпизод болезни на входе."""

    start_date: date
    title: str = Field(min_length=1)
    end_date: date | None = None
    status: str | None = None
    notes: str | None = None


class Illness(BaseModel):
    id: int
    person_id: int
    start_date: date
    title: str
    end_date: date | None = None
    status: str | None = None
    notes: str | None = None


class RecommendationCreate(BaseModel):
    """Рекомендация / контрольная точка на входе."""

    text: str = Field(min_length=1)
    kind: str | None = None  # medication | control | referral | lifestyle
    due_date: date | None = None
    status: str = "open"


class Recommendation(BaseModel):
    id: int
    person_id: int
    visit_id: int | None = None
    text: str
    kind: str | None = None
    due_date: date | None = None
    status: str


class VisitCreate(BaseModel):
    """Визит к врачу на входе вместе со своими рекомендациями."""

    date: date
    doctor_name: str | None = None
    specialty: str | None = None
    clinic: str | None = None
    conclusion: str | None = None
    notes: str | None = None
    source: str = "manual"
    recommendations: list[RecommendationCreate] = Field(default_factory=list)


class Visit(BaseModel):
    id: int
    person_id: int
    date: date
    doctor_name: str | None = None
    specialty: str | None = None
    clinic: str | None = None
    conclusion: str | None = None
    notes: str | None = None
    source: str
    document_path: str | None = None
    recommendations: list[Recommendation] = Field(default_factory=list)
