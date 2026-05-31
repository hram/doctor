from pathlib import PurePosixPath

from app.repositories.visits import VisitRepository
from app.schemas import Visit, VisitCreate
from app.services.documents import build_document_store, canonical_relpath


class VisitService:
    """Бизнес-логика визитов (CRUD по метаданным + привязка скана документа)."""

    def __init__(self, repository: VisitRepository | None = None) -> None:
        self._repository = repository or VisitRepository()

    def list_for_person(self, person_id: int) -> list[Visit]:
        return self._repository.list_by_person(person_id)

    def get(self, visit_id: int) -> Visit | None:
        return self._repository.get(visit_id)

    def create(self, person_id: int, data: VisitCreate) -> int:
        return self._repository.upsert(person_id, data)

    def update(self, visit_id: int, data: VisitCreate) -> None:
        self._repository.update(visit_id, data)

    def delete(self, visit_id: int) -> None:
        self._repository.delete(visit_id)

    def _relpath(self, v: Visit, person_name: str, ext: str) -> str:
        # Заголовок документа визита — из специальности; токен vid отличает от анализов.
        title = v.specialty or "визит"
        return canonical_relpath(person_name, v.date, title, v.id, ext, id_prefix="vid")

    def attach_uploaded(
        self, visit_id: int, person_name: str, data: bytes, ext: str
    ) -> None:
        v = self._repository.get(visit_id)
        if v is None:
            return
        rel = self._relpath(v, person_name, ext or ".pdf")
        build_document_store().write(rel, data)
        self._repository.set_document_path(v.id, rel)

    def attach_from_inbox(
        self, visit_id: int, person_name: str, inbox_name: str
    ) -> None:
        v = self._repository.get(visit_id)
        if v is None:
            return
        ext = PurePosixPath(inbox_name).suffix or ".pdf"
        rel = self._relpath(v, person_name, ext)
        build_document_store().move_from_inbox(inbox_name, rel)
        self._repository.set_document_path(v.id, rel)
