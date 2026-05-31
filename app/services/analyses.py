from pathlib import PurePosixPath

from app.repositories.analyses import AnalysisRepository
from app.repositories.markers import MarkerRepository
from app.schemas import Analysis, AnalysisCreate, MeasurementCreate
from app.services.documents import build_document_store, canonical_relpath


def compute_flag(m: MeasurementCreate) -> str | None:
    """Вычислить flag по значению и референсу, если он не задан явно.

    Качественные результаты (только value_text) и записи без референса
    остаются без флага — их интерпретирует источник или человек.
    """
    if m.flag:
        return m.flag
    if m.value_num is None:
        return None
    if m.ref_high is not None and m.value_num > m.ref_high:
        return "high"
    if m.ref_low is not None and m.value_num < m.ref_low:
        return "low"
    if m.ref_low is not None or m.ref_high is not None:
        return "normal"
    return None


class AnalysisService:
    """Бизнес-логика анализов: обогащение измерений референсом из справочника,
    проставление флагов отклонений, запись через репозиторий."""

    def __init__(
        self,
        repository: AnalysisRepository | None = None,
        marker_repository: MarkerRepository | None = None,
    ) -> None:
        self._repository = repository or AnalysisRepository()
        self._markers = marker_repository or MarkerRepository()

    def list_for_person(self, person_id: int) -> list[Analysis]:
        return self._repository.list_by_person(person_id)

    def get(self, analysis_id: int) -> Analysis | None:
        return self._repository.get(analysis_id)

    def update(self, analysis_id: int, data: AnalysisCreate) -> None:
        self._repository.update(analysis_id, data)

    def delete(self, analysis_id: int) -> None:
        self._repository.delete(analysis_id)

    def set_document_path(self, analysis_id: int, relpath: str) -> None:
        self._repository.set_document_path(analysis_id, relpath)

    def attach_uploaded(
        self, analysis_id: int, person_name: str, data: bytes, ext: str
    ) -> None:
        """Привязать загруженный из браузера файл к анализу."""
        a = self._repository.get(analysis_id)
        if a is None:
            return
        rel = canonical_relpath(person_name, a.date, a.title, a.id, ext or ".pdf")
        store = build_document_store()
        store.write(rel, data)
        self._repository.set_document_path(a.id, rel)

    def attach_from_inbox(
        self, analysis_id: int, person_name: str, inbox_name: str
    ) -> None:
        """Привязать скан из «входящих»: перенести в каноническое место."""
        a = self._repository.get(analysis_id)
        if a is None:
            return
        ext = PurePosixPath(inbox_name).suffix or ".pdf"
        rel = canonical_relpath(person_name, a.date, a.title, a.id, ext)
        store = build_document_store()
        store.move_from_inbox(inbox_name, rel)
        self._repository.set_document_path(a.id, rel)

    def create(self, person_id: int, data: AnalysisCreate) -> int:
        """Создать/обновить анализ. Единица/референс подтягиваются из справочника
        показателей (если источник не задал свои), затем проставляется флаг
        отклонения — в одном месте, чтобы импорт и ручной ввод вели себя одинаково."""
        catalog = {m.code: m for m in self._markers.list()}
        for m in data.measurements:
            marker = catalog.get(m.marker_code)
            if marker is not None:
                if m.unit is None:
                    m.unit = marker.unit
                if m.ref_low is None:
                    m.ref_low = marker.ref_low
                if m.ref_high is None:
                    m.ref_high = marker.ref_high
            m.flag = compute_flag(m)
        return self._repository.upsert(person_id, data)
