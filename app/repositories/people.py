from app.db.database import get_connection
from app.schemas import Person, PersonCreate

_COLS = "id, name, full_name, birth_date, role, sex, notes, created_at"


class PersonRepository:
    """Доступ к данным людей. Единственное место с SQL по таблице ``person``."""

    def list(self) -> list[Person]:
        with get_connection() as conn:
            rows = conn.execute(
                f"SELECT {_COLS} FROM person ORDER BY birth_date IS NULL, birth_date"
            ).fetchall()
        return [Person(**dict(row)) for row in rows]

    def get(self, person_id: int) -> Person | None:
        with get_connection() as conn:
            row = conn.execute(
                f"SELECT {_COLS} FROM person WHERE id = ?", (person_id,)
            ).fetchone()
        return Person(**dict(row)) if row else None

    def get_by_name(self, name: str) -> Person | None:
        with get_connection() as conn:
            row = conn.execute(
                f"SELECT {_COLS} FROM person WHERE name = ?", (name,)
            ).fetchone()
        return Person(**dict(row)) if row else None

    def upsert(self, data: PersonCreate) -> Person:
        """Создать или обновить человека по натуральному ключу ``name``.

        Идемпотентно: повторный вызов с тем же ``name`` обновляет запись, а не
        плодит дубль. Используется и импортом, и ручным вводом.
        """
        birth = data.birth_date.isoformat() if data.birth_date else None
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM person WHERE name = ?", (data.name,)
            ).fetchone()
            if existing:
                person_id = int(existing["id"])
                conn.execute(
                    "UPDATE person SET full_name = ?, birth_date = ?, role = ?, "
                    "sex = ?, notes = ? WHERE id = ?",
                    (data.full_name, birth, data.role, data.sex, data.notes,
                     person_id),
                )
            else:
                cursor = conn.execute(
                    "INSERT INTO person (name, full_name, birth_date, role, sex, "
                    "notes) VALUES (?, ?, ?, ?, ?, ?)",
                    (data.name, data.full_name, birth, data.role, data.sex,
                     data.notes),
                )
                assert cursor.lastrowid is not None
                person_id = cursor.lastrowid
            row = conn.execute(
                f"SELECT {_COLS} FROM person WHERE id = ?", (person_id,)
            ).fetchone()
        return Person(**dict(row))
