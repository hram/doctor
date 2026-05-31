from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.ingestion.analizy import EXAMPLE_SEED, import_seed
from app.services.analyses import AnalysisService
from app.services.documents import (
    LocalDocumentStore,
    build_document_store,
    canonical_relpath,
)


def _first_analysis_id(client: TestClient) -> int:
    people = client.get("/api/people").json()
    child = next(p for p in people if p["name"] == "Ребёнок")
    timeline = client.get(f"/api/person/{child['id']}/timeline").json()
    return next(e["ref_id"] for e in timeline if e["kind"] == "analysis")


def test_canonical_relpath_contains_id() -> None:
    rel = canonical_relpath("Катя", date(2026, 3, 27), "Общий анализ крови", 9)
    assert rel.startswith("катя/")
    assert "2026-03-27" in rel
    assert rel.endswith("aid9.pdf")


def test_local_store_rejects_traversal(tmp_path: Path) -> None:
    store = LocalDocumentStore(tmp_path, tmp_path / "inbox")
    assert store.read(None) is None
    assert store.read("../../etc/passwd") is None
    assert store.read("/etc/passwd") is None
    assert store.read("missing.pdf") is None

    store.write("Ребёнок/x.pdf", b"%PDF-1.4")
    assert store.read("Ребёнок/x.pdf") == b"%PDF-1.4"

    with pytest.raises(ValueError):
        store.write("../escape.pdf", b"x")


def test_default_backend_is_local() -> None:
    get_settings.cache_clear()
    assert isinstance(build_document_store(), LocalDocumentStore)


def test_document_404_without_attachment(client: TestClient) -> None:
    import_seed(EXAMPLE_SEED)
    aid = _first_analysis_id(client)
    assert client.get(f"/documents/{aid}").status_code == 404
    assert client.get("/documents/99999").status_code == 404


def test_view_attached_document(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTAL_DOCUMENTS_ROOT", str(tmp_path / "docs"))
    get_settings.cache_clear()

    import_seed(EXAMPLE_SEED)
    aid = _first_analysis_id(client)

    # Привязываем документ так же, как scripts.organize_documents.
    svc = AnalysisService()
    analysis = svc.get(aid)
    assert analysis is not None
    store = build_document_store()
    rel = store.canonical_relpath("Ребёнок", analysis.date, analysis.title, analysis.id)
    store.write(rel, b"%PDF-1.4 example")
    svc.set_document_path(analysis.id, rel)

    child = next(p for p in client.get("/api/people").json() if p["name"] == "Ребёнок")
    page = client.get(f"/person/{child['id']}")
    assert "исходный документ" in page.text

    resp = client.get(f"/documents/{aid}")
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")

    get_settings.cache_clear()
