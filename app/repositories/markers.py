from app.db.database import get_connection
from app.schemas import Marker

_COLS = "id, code, name, unit, ref_low, ref_high"


class MarkerRepository:
    """Доступ к справочнику показателей (таблица ``marker``)."""

    def list(self) -> list[Marker]:
        with get_connection() as conn:
            rows = conn.execute(f"SELECT {_COLS} FROM marker ORDER BY name").fetchall()
        return [Marker(**dict(row)) for row in rows]

    def get_by_code(self, code: str) -> Marker | None:
        with get_connection() as conn:
            row = conn.execute(
                f"SELECT {_COLS} FROM marker WHERE code = ?", (code,)
            ).fetchone()
        return Marker(**dict(row)) if row else None

    def id_by_code(self) -> dict[str, int]:
        """Карта code -> id для быстрой привязки измерений при импорте."""
        with get_connection() as conn:
            rows = conn.execute("SELECT code, id FROM marker").fetchall()
        return {row["code"]: row["id"] for row in rows}
