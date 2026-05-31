from fastapi.testclient import TestClient

from app.ingestion.analizy import EXAMPLE_SEED, import_seed


def test_index_lists_people(client: TestClient) -> None:
    import_seed(EXAMPLE_SEED)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Ребёнок" in resp.text
    assert "Родитель" in resp.text


def test_person_page_shows_timeline(client: TestClient) -> None:
    import_seed(EXAMPLE_SEED)
    people = client.get("/api/people").json()
    child_id = next(p["id"] for p in people if p["name"] == "Ребёнок")
    resp = client.get(f"/person/{child_id}")
    assert resp.status_code == 200
    # Хронология содержит ключевые события и показатели.
    assert "ОРВИ" in resp.text
    assert "АСЛО" in resp.text


def test_person_page_404(client: TestClient) -> None:
    assert client.get("/person/999").status_code == 404
