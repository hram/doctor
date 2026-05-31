from app.repositories.analyses import AnalysisRepository
from app.repositories.markers import MarkerRepository
from app.schemas import Analysis, AnalysisCreate, MeasurementCreate


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
