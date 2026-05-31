from app.db.database import get_connection
from app.schemas import Illness, IllnessCreate

_COLS = "id, person_id, start_date, title, end_date, status, notes"


class IllnessRepository:
    """Доступ к эпизодам болезней (таблица ``illness``)."""

    def list_by_person(self, person_id: int) -> list[Illness]:
        with get_connection() as conn:
            rows = conn.execute(
                f"SELECT {_COLS} FROM illness WHERE person_id = ? "
                "ORDER BY start_date, id",
                (person_id,),
            ).fetchall()
        return [Illness(**dict(row)) for row in rows]

    def upsert(self, person_id: int, data: IllnessCreate) -> int:
        """Создать/обновить эпизод по ключу (person_id, start_date, title)."""
        start = data.start_date.isoformat()
        end = data.end_date.isoformat() if data.end_date else None
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM illness WHERE person_id = ? AND start_date = ? AND "
                "title = ?",
                (person_id, start, data.title),
            ).fetchone()
            if existing:
                illness_id = int(existing["id"])
                conn.execute(
                    "UPDATE illness SET end_date = ?, status = ?, notes = ? "
                    "WHERE id = ?",
                    (end, data.status, data.notes, illness_id),
                )
            else:
                cursor = conn.execute(
                    "INSERT INTO illness (person_id, start_date, title, end_date, "
                    "status, notes) VALUES (?, ?, ?, ?, ?, ?)",
                    (person_id, start, data.title, end, data.status, data.notes),
                )
                assert cursor.lastrowid is not None
                illness_id = cursor.lastrowid
        return illness_id
