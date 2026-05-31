from typing import Any

from app.db.database import get_connection


class RelationRepository:
    """Доступ к семейным связям (таблица ``relation``)."""

    def upsert(self, person_id: int, relative_id: int, kind: str) -> None:
        """Создать связь, если её ещё нет (идемпотентно по UNIQUE-ключу)."""
        with get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO relation (person_id, relative_id, kind) "
                "VALUES (?, ?, ?)",
                (person_id, relative_id, kind),
            )

    def list_for_person(self, person_id: int) -> list[dict[str, Any]]:
        """Связи человека вместе с именем родственника."""
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT r.kind, p.id AS relative_id, p.name AS relative_name "
                "FROM relation r JOIN person p ON p.id = r.relative_id "
                "WHERE r.person_id = ?",
                (person_id,),
            ).fetchall()
        return [dict(row) for row in rows]
