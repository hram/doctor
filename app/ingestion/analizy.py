"""Импорт нормализованного среза данных из пространства analizy.

Адаптер читает ``analizy_seed.json`` (нормализованный срез markers.csv /
master-markers.md) и пишет в БД через сервисы и репозитории. Идемпотентно:
повторный запуск обновляет записи по натуральным ключам, а не плодит дубли.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from app.repositories.illnesses import IllnessRepository
from app.repositories.relations import RelationRepository
from app.repositories.visits import VisitRepository
from app.schemas import (
    AnalysisCreate,
    IllnessCreate,
    PersonCreate,
    VisitCreate,
)
from app.services.analyses import AnalysisService
from app.services.people import PersonService

_DIR = Path(__file__).resolve().parent
# Реальные данные семьи (в .gitignore, только локально).
DEFAULT_SEED = _DIR / "analizy_seed.json"
# Анонимный пример структуры (в репозитории); на него опираются тесты.
EXAMPLE_SEED = _DIR / "analizy_seed.example.json"


@dataclass
class ImportStats:
    """Счётчики того, что было загружено (для отчёта в CLI и проверки в тестах)."""

    people: int = 0
    analyses: int = 0
    visits: int = 0
    illnesses: int = 0
    relations: int = 0


def import_seed(seed_path: Path | None = None) -> ImportStats:
    """Загрузить seed в БД. Возвращает статистику загруженных сущностей."""
    path = seed_path or DEFAULT_SEED
    data = json.loads(path.read_text(encoding="utf-8"))

    people_service = PersonService()
    analysis_service = AnalysisService()
    visit_repo = VisitRepository()
    illness_repo = IllnessRepository()
    relation_repo = RelationRepository()

    stats = ImportStats()
    name_to_id: dict[str, int] = {}

    for raw_person in data.get("people", []):
        person = people_service.upsert_person(
            PersonCreate(
                name=raw_person["name"],
                full_name=raw_person.get("full_name"),
                birth_date=raw_person.get("birth_date"),
                role=raw_person.get("role", "child"),
                sex=raw_person.get("sex"),
                notes=raw_person.get("notes"),
            )
        )
        name_to_id[person.name] = person.id
        stats.people += 1

        for raw_analysis in raw_person.get("analyses", []):
            analysis_service.create(person.id, AnalysisCreate(**raw_analysis))
            stats.analyses += 1

        for raw_visit in raw_person.get("visits", []):
            visit_repo.upsert(person.id, VisitCreate(**raw_visit))
            stats.visits += 1

        for raw_illness in raw_person.get("illnesses", []):
            illness_repo.upsert(person.id, IllnessCreate(**raw_illness))
            stats.illnesses += 1

    for raw_rel in data.get("relations", []):
        person_id = name_to_id.get(raw_rel["person"])
        relative_id = name_to_id.get(raw_rel["relative"])
        if person_id and relative_id:
            relation_repo.upsert(person_id, relative_id, raw_rel["kind"])
            stats.relations += 1

    return stats
