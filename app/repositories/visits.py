from app.db.database import get_connection
from app.schemas import Recommendation, Visit, VisitCreate

_VISIT_COLS = (
    "id, person_id, date, doctor_name, specialty, clinic, conclusion, notes, source"
)
_REC_COLS = "id, person_id, visit_id, text, kind, due_date, status"


class VisitRepository:
    """Доступ к визитам и их рекомендациям (таблицы ``visit`` + ``recommendation``)."""

    def list_by_person(self, person_id: int) -> list[Visit]:
        with get_connection() as conn:
            rows = conn.execute(
                f"SELECT {_VISIT_COLS} FROM visit WHERE person_id = ? "
                "ORDER BY date, id",
                (person_id,),
            ).fetchall()
            visits = [Visit(**dict(row)) for row in rows]
            for visit in visits:
                rec_rows = conn.execute(
                    f"SELECT {_REC_COLS} FROM recommendation WHERE visit_id = ? "
                    "ORDER BY id",
                    (visit.id,),
                ).fetchall()
                visit.recommendations = [Recommendation(**dict(r)) for r in rec_rows]
        return visits

    def upsert(self, person_id: int, data: VisitCreate) -> int:
        """Создать/обновить визит по ключу (person_id, date, specialty, doctor_name)
        и его рекомендации. Возвращает id визита. Идемпотентно."""
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM visit WHERE person_id = ? AND date = ? AND "
                "specialty IS ? AND doctor_name IS ?",
                (person_id, data.date.isoformat(), data.specialty, data.doctor_name),
            ).fetchone()
            if existing:
                visit_id = int(existing["id"])
                conn.execute(
                    "UPDATE visit SET clinic = ?, conclusion = ?, notes = ?, "
                    "source = ? WHERE id = ?",
                    (data.clinic, data.conclusion, data.notes, data.source, visit_id),
                )
            else:
                cursor = conn.execute(
                    "INSERT INTO visit (person_id, date, doctor_name, specialty, "
                    "clinic, conclusion, notes, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (person_id, data.date.isoformat(), data.doctor_name,
                     data.specialty, data.clinic, data.conclusion, data.notes,
                     data.source),
                )
                assert cursor.lastrowid is not None
                visit_id = cursor.lastrowid

            for rec in data.recommendations:
                due = rec.due_date.isoformat() if rec.due_date else None
                row = conn.execute(
                    "SELECT id FROM recommendation WHERE person_id = ? AND text = ? "
                    "AND visit_id IS ?",
                    (person_id, rec.text, visit_id),
                ).fetchone()
                if row:
                    conn.execute(
                        "UPDATE recommendation SET kind = ?, due_date = ?, status = ? "
                        "WHERE id = ?",
                        (rec.kind, due, rec.status, row["id"]),
                    )
                else:
                    conn.execute(
                        "INSERT INTO recommendation (person_id, visit_id, text, kind, "
                        "due_date, status) VALUES (?, ?, ?, ?, ?, ?)",
                        (person_id, visit_id, rec.text, rec.kind, due, rec.status),
                    )
        return visit_id
