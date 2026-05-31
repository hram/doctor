from fastapi.testclient import TestClient

from app.ingestion.analizy import EXAMPLE_SEED, import_seed


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_markers_catalog_seeded(client: TestClient) -> None:
    """Справочник показателей сидируется на старте (lifespan → init_db)."""
    codes = {m["code"] for m in client.get("/api/markers").json()}
    assert {"aslo", "iron", "vitamin_d", "hgb", "wbc"} <= codes


def test_people_empty_before_import(client: TestClient) -> None:
    assert client.get("/api/people").json() == []


def test_timeline_sorted_desc(client: TestClient) -> None:
    import_seed(EXAMPLE_SEED)
    people = client.get("/api/people").json()
    child_id = next(p["id"] for p in people if p["name"] == "Ребёнок")
    timeline = client.get(f"/api/person/{child_id}/timeline").json()
    dates = [e["date"] for e in timeline]
    assert dates == sorted(dates, reverse=True)
    kinds = {e["kind"] for e in timeline}
    assert {"analysis", "visit", "illness"} <= kinds


def test_timeline_404_for_unknown_person(client: TestClient) -> None:
    assert client.get("/api/person/999/timeline").status_code == 404
