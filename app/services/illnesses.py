from app.repositories.illnesses import IllnessRepository
from app.schemas import Illness, IllnessCreate


class IllnessService:
    """Бизнес-логика эпизодов болезней (CRUD)."""

    def __init__(self, repository: IllnessRepository | None = None) -> None:
        self._repository = repository or IllnessRepository()

    def list_for_person(self, person_id: int) -> list[Illness]:
        return self._repository.list_by_person(person_id)

    def get(self, illness_id: int) -> Illness | None:
        return self._repository.get(illness_id)

    def create(self, person_id: int, data: IllnessCreate) -> int:
        return self._repository.upsert(person_id, data)

    def update(self, illness_id: int, data: IllnessCreate) -> None:
        self._repository.update(illness_id, data)

    def delete(self, illness_id: int) -> None:
        self._repository.delete(illness_id)
