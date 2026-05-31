from app.repositories.analyses import AnalysisRepository
from app.repositories.illnesses import IllnessRepository
from app.repositories.people import PersonRepository
from app.repositories.visits import VisitRepository
from app.schemas import (
    Analysis,
    Measurement,
    Person,
    PersonCreate,
    TimelineEvent,
)

# Человекочитаемые ярлыки флагов отклонений.
_FLAG_LABEL = {
    "high": "↑ выше нормы",
    "low": "↓ ниже нормы",
    "positive": "положительно",
    "negative": "отрицательно",
    "normal": "норма",
}


def _measurement_brief(m: Measurement) -> str:
    """Короткая запись измерения для ленты: «АСЛО 372.5 ↑ выше нормы»."""
    value = m.value_text if m.value_num is None else _fmt_num(m.value_num)
    name = m.marker_name or m.marker_code or "показатель"
    parts = [name, str(value)]
    if m.flag and m.flag != "normal":
        parts.append(_FLAG_LABEL.get(m.flag, m.flag))
    return " ".join(parts)


def _fmt_num(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)


class PersonService:
    """Бизнес-логика людей и сборка единой хронологии событий."""

    def __init__(
        self,
        repository: PersonRepository | None = None,
        analysis_repository: AnalysisRepository | None = None,
        visit_repository: VisitRepository | None = None,
        illness_repository: IllnessRepository | None = None,
    ) -> None:
        self._repository = repository or PersonRepository()
        self._analyses = analysis_repository or AnalysisRepository()
        self._visits = visit_repository or VisitRepository()
        self._illnesses = illness_repository or IllnessRepository()

    def list_people(self) -> list[Person]:
        return self._repository.list()

    def get_person(self, person_id: int) -> Person | None:
        return self._repository.get(person_id)

    def upsert_person(self, data: PersonCreate) -> Person:
        return self._repository.upsert(data)

    def get_timeline(self, person_id: int) -> list[TimelineEvent]:
        """Свести анализы, визиты и болезни в единую ленту, отсортированную по дате
        (от новых к старым). Рекомендации идут вложенными в свой визит."""
        events: list[TimelineEvent] = []

        for a in self._analyses.list_by_person(person_id):
            events.append(self._analysis_event(a))

        for v in self._visits.list_by_person(person_id):
            events.append(
                TimelineEvent(
                    date=v.date,
                    kind="visit",
                    title=v.specialty or "Визит",
                    detail=v.conclusion,
                    ref_id=v.id,
                    extra={
                        "doctor_name": v.doctor_name,
                        "specialty": v.specialty,
                        "clinic": v.clinic,
                        "document_path": v.document_path,
                        "recommendations": [
                            {"text": r.text, "kind": r.kind,
                             "due_date": r.due_date.isoformat() if r.due_date else None,
                             "status": r.status}
                            for r in v.recommendations
                        ],
                    },
                )
            )

        for i in self._illnesses.list_by_person(person_id):
            events.append(
                TimelineEvent(
                    date=i.start_date,
                    kind="illness",
                    title=i.title,
                    detail=i.notes,
                    ref_id=i.id,
                    extra={
                        "end_date": i.end_date.isoformat() if i.end_date else None,
                        "status": i.status,
                    },
                )
            )

        events.sort(key=lambda e: (e.date, e.kind), reverse=True)
        return events

    def _analysis_event(self, a: Analysis) -> TimelineEvent:
        briefs = [_measurement_brief(m) for m in a.measurements]
        # Если показателей нет (УЗИ, ЭХО-КГ и пр.) — показываем текстовое
        # заключение из notes, а уже потом откатываемся на категорию.
        detail = "; ".join(briefs) if briefs else (a.notes or a.category)
        return TimelineEvent(
            date=a.date,
            kind="analysis",
            title=a.title,
            detail=detail,
            ref_id=a.id,
            extra={
                "category": a.category,
                "lab": a.lab,
                "source": a.source,
                "document_path": a.document_path,
                "measurements": [m.model_dump() for m in a.measurements],
            },
        )
