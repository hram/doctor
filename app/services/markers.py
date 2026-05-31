from typing import Any

from app.repositories.analyses import AnalysisRepository
from app.repositories.markers import MarkerRepository
from app.schemas import Marker


class MarkerService:
    """Справочник показателей и ряды значений для графиков динамики."""

    def __init__(
        self,
        repository: MarkerRepository | None = None,
        analysis_repository: AnalysisRepository | None = None,
    ) -> None:
        self._repository = repository or MarkerRepository()
        self._analyses = analysis_repository or AnalysisRepository()

    def list_markers(self) -> list[Marker]:
        return self._repository.list()

    def series_for_person(self, person_id: int) -> list[dict[str, Any]]:
        """Числовые измерения человека, сгруппированные по показателю.

        Формат удобен для отрисовки графиков (по одному ряду на показатель)::

            [{"code", "name", "unit", "ref_low", "ref_high",
              "points": [{"date", "value", "flag"}, ...]}, ...]
        """
        series: dict[str, dict[str, Any]] = {}
        for row in self._analyses.numeric_series(person_id):
            code = row["marker_code"]
            s = series.setdefault(
                code,
                {
                    "code": code,
                    "name": row["marker_name"],
                    "unit": row["marker_unit"],
                    "ref_low": row["ref_low"],
                    "ref_high": row["ref_high"],
                    "points": [],
                },
            )
            s["points"].append(
                {
                    "date": row["date"],
                    "value": row["value_num"],
                    "flag": row["flag"],
                }
            )
        return list(series.values())
