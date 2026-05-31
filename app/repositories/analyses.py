import sqlite3
from typing import Any

from app.db.database import get_connection
from app.schemas import Analysis, AnalysisCreate, Measurement

_ANALYSIS_COLS = (
    "id, person_id, date, category, title, lab, source, source_ref, "
    "document_path, notes"
)


class AnalysisRepository:
    """Доступ к анализам и их измерениям (таблицы ``analysis`` + ``measurement``).

    Аггрегат: измерения не существуют без анализа, поэтому живут в одном
    репозитории и пишутся в одной транзакции.
    """

    def list_by_person(self, person_id: int) -> list[Analysis]:
        with get_connection() as conn:
            rows = conn.execute(
                f"SELECT {_ANALYSIS_COLS} FROM analysis WHERE person_id = ? "
                "ORDER BY date, id",
                (person_id,),
            ).fetchall()
            analyses = [Analysis(**dict(row)) for row in rows]
            for analysis in analyses:
                analysis.measurements = self._measurements(conn, analysis.id)
        return analyses

    def numeric_series(self, person_id: int) -> list[dict[str, Any]]:
        """Все числовые измерения человека с датой и кодом показателя.

        Задел под графики динамики: сервис группирует это по marker_code в ряды.
        """
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT a.date AS date, mk.code AS marker_code, mk.name AS marker_name, "
                "mk.unit AS marker_unit, m.value_num, m.ref_low, m.ref_high, m.flag "
                "FROM measurement m "
                "JOIN analysis a ON a.id = m.analysis_id "
                "JOIN marker mk ON mk.id = m.marker_id "
                "WHERE a.person_id = ? AND m.value_num IS NOT NULL "
                "ORDER BY mk.name, a.date",
                (person_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _measurements(
        self, conn: sqlite3.Connection, analysis_id: int
    ) -> list[Measurement]:
        rows = conn.execute(
            "SELECT m.id, mk.code AS marker_code, mk.name AS marker_name, "
            "m.value_num, m.value_text, m.unit, m.ref_low, m.ref_high, m.flag "
            "FROM measurement m LEFT JOIN marker mk ON mk.id = m.marker_id "
            "WHERE m.analysis_id = ? ORDER BY m.id",
            (analysis_id,),
        ).fetchall()
        return [Measurement(**dict(row)) for row in rows]

    def upsert(self, person_id: int, data: AnalysisCreate) -> int:
        """Создать/обновить анализ по ключу (person_id, date, title) и его измерения.

        Возвращает id анализа. Идемпотентно: повторный импорт обновляет, не дублит.
        """
        with get_connection() as conn:
            marker_ids = {
                row["code"]: row["id"]
                for row in conn.execute("SELECT code, id FROM marker").fetchall()
            }
            existing = conn.execute(
                "SELECT id FROM analysis WHERE person_id = ? AND date = ? AND title = ?",
                (person_id, data.date.isoformat(), data.title),
            ).fetchone()
            if existing:
                analysis_id = int(existing["id"])
                conn.execute(
                    "UPDATE analysis SET category = ?, lab = ?, source = ?, "
                    "source_ref = ?, document_path = ?, notes = ? WHERE id = ?",
                    (data.category, data.lab, data.source, data.source_ref,
                     data.document_path, data.notes, analysis_id),
                )
            else:
                cursor = conn.execute(
                    "INSERT INTO analysis (person_id, date, category, title, lab, "
                    "source, source_ref, document_path, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (person_id, data.date.isoformat(), data.category, data.title,
                     data.lab, data.source, data.source_ref, data.document_path,
                     data.notes),
                )
                assert cursor.lastrowid is not None
                analysis_id = cursor.lastrowid

            for m in data.measurements:
                marker_id = marker_ids.get(m.marker_code)
                row = conn.execute(
                    "SELECT id FROM measurement WHERE analysis_id = ? AND "
                    "marker_id IS ?",
                    (analysis_id, marker_id),
                ).fetchone()
                if row:
                    conn.execute(
                        "UPDATE measurement SET value_num = ?, value_text = ?, "
                        "unit = ?, ref_low = ?, ref_high = ?, flag = ? WHERE id = ?",
                        (m.value_num, m.value_text, m.unit, m.ref_low, m.ref_high,
                         m.flag, row["id"]),
                    )
                else:
                    conn.execute(
                        "INSERT INTO measurement (analysis_id, marker_id, value_num, "
                        "value_text, unit, ref_low, ref_high, flag) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (analysis_id, marker_id, m.value_num, m.value_text, m.unit,
                         m.ref_low, m.ref_high, m.flag),
                    )
        return analysis_id
