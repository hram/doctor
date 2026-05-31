"""Тесты импорта: идемпотентность и корректность значений.

Работают на анонимном analizy_seed.example.json — реальные данные семьи в
репозиторий не коммитятся, поэтому тесты от них не зависят.
"""

from fastapi.testclient import TestClient

from app.ingestion.analizy import EXAMPLE_SEED, import_seed


def _person_id(client: TestClient, name: str) -> int:
    people = client.get("/api/people").json()
    return next(p["id"] for p in people if p["name"] == name)


def test_import_loads_people(client: TestClient) -> None:
    stats = import_seed(EXAMPLE_SEED)
    assert stats.people == 2
    assert stats.relations == 1

    names = {p["name"] for p in client.get("/api/people").json()}
    assert names == {"Ребёнок", "Родитель"}


def test_import_is_idempotent(client: TestClient) -> None:
    """Повторный импорт не плодит дубли (upsert по натуральным ключам)."""
    first = import_seed(EXAMPLE_SEED)
    child_id = _person_id(client, "Ребёнок")
    timeline_len_1 = len(client.get(f"/api/person/{child_id}/timeline").json())

    second = import_seed(EXAMPLE_SEED)
    timeline_len_2 = len(client.get(f"/api/person/{child_id}/timeline").json())

    assert (first.people, first.analyses, first.visits, first.illnesses) == (
        second.people,
        second.analyses,
        second.visits,
        second.illnesses,
    )
    assert len(client.get("/api/people").json()) == 2
    assert timeline_len_1 == timeline_len_2


def test_aslo_above_reference_flagged_high(client: TestClient) -> None:
    """АСЛО 250 при референсе из справочника 0–200 должен помечаться как повышенный."""
    import_seed(EXAMPLE_SEED)
    child_id = _person_id(client, "Ребёнок")
    series = client.get(f"/api/person/{child_id}/markers").json()
    aslo = next(s for s in series if s["code"] == "aslo")
    point = aslo["points"][0]
    assert point["value"] == 250.0
    assert point["flag"] == "high"


def test_cbc_values_imported(client: TestClient) -> None:
    """Показатели ОАК (гемоглобин и пр.) попадают в ряды значений."""
    import_seed(EXAMPLE_SEED)
    child_id = _person_id(client, "Ребёнок")
    codes = {s["code"] for s in client.get(f"/api/person/{child_id}/markers").json()}
    assert {"hgb", "wbc", "plt"} <= codes
