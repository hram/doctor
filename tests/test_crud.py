"""Тесты ручного CRUD (формы) и привязки скана при добавлении анализа."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.ingestion.analizy import EXAMPLE_SEED, import_seed


def _child_id(client: TestClient) -> int:
    people = client.get("/api/people").json()
    return next(p["id"] for p in people if p["name"] == "Ребёнок")


def _find_event(client: TestClient, person_id: int, kind: str, title: str) -> dict:
    timeline = client.get(f"/api/person/{person_id}/timeline").json()
    return next(e for e in timeline if e["kind"] == kind and e["title"] == title)


def test_create_analysis_minimal(client: TestClient) -> None:
    import_seed(EXAMPLE_SEED)
    pid = _child_id(client)
    resp = client.post(
        f"/person/{pid}/analysis",
        data={"date": "2026-05-30", "title": "Рентген грудной клетки", "category": "рентген"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    ev = _find_event(client, pid, "analysis", "Рентген грудной клетки")
    assert ev["extra"]["category"] == "рентген"
    assert ev["extra"]["document_path"] is None


def test_create_analysis_with_inbox_scan(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTAL_DOCUMENTS_ROOT", str(tmp_path / "docs"))
    monkeypatch.setenv("PORTAL_DOCUMENTS_INBOX", str(tmp_path / "inbox"))
    get_settings.cache_clear()
    (tmp_path / "inbox").mkdir()
    (tmp_path / "inbox" / "scan_rentgen.pdf").write_bytes(b"%PDF-1.4 rentgen")

    import_seed(EXAMPLE_SEED)
    pid = _child_id(client)

    # «Входящие» видны в форме.
    form = client.get(f"/person/{pid}/analysis/new")
    assert "scan_rentgen.pdf" in form.text

    client.post(
        f"/person/{pid}/analysis",
        data={"date": "2026-05-30", "title": "Рентген", "category": "рентген",
              "inbox_name": "scan_rentgen.pdf"},
        follow_redirects=False,
    )
    ev = _find_event(client, pid, "analysis", "Рентген")
    assert ev["extra"]["document_path"] is not None

    # Файл переехал из «входящих» и отдаётся.
    assert not (tmp_path / "inbox" / "scan_rentgen.pdf").exists()
    resp = client.get(f"/documents/{ev['ref_id']}")
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")

    get_settings.cache_clear()


def test_create_analysis_with_upload(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTAL_DOCUMENTS_ROOT", str(tmp_path / "docs"))
    monkeypatch.setenv("PORTAL_DOCUMENTS_INBOX", str(tmp_path / "inbox"))
    get_settings.cache_clear()

    import_seed(EXAMPLE_SEED)
    pid = _child_id(client)
    client.post(
        f"/person/{pid}/analysis",
        data={"date": "2026-05-30", "title": "Рентген загруженный", "category": "рентген"},
        files={"upload": ("xray.pdf", b"%PDF-1.4 uploaded", "application/pdf")},
        follow_redirects=False,
    )
    ev = _find_event(client, pid, "analysis", "Рентген загруженный")
    assert ev["extra"]["document_path"] is not None
    resp = client.get(f"/documents/{ev['ref_id']}")
    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.4 uploaded"

    get_settings.cache_clear()


def test_edit_and_delete_analysis(client: TestClient) -> None:
    import_seed(EXAMPLE_SEED)
    pid = _child_id(client)
    client.post(
        f"/person/{pid}/analysis",
        data={"date": "2026-05-30", "title": "Черновик", "category": "кровь"},
        follow_redirects=False,
    )
    ev = _find_event(client, pid, "analysis", "Черновик")
    aid = ev["ref_id"]

    # edit
    client.post(
        f"/analysis/{aid}",
        data={"date": "2026-05-30", "title": "Исправлено", "category": "кровь"},
        follow_redirects=False,
    )
    titles = [e["title"] for e in client.get(f"/api/person/{pid}/timeline").json()]
    assert "Исправлено" in titles and "Черновик" not in titles

    # delete
    resp = client.post(f"/analysis/{aid}/delete", follow_redirects=False)
    assert resp.status_code == 303
    titles = [e["title"] for e in client.get(f"/api/person/{pid}/timeline").json()]
    assert "Исправлено" not in titles


def test_visit_crud(client: TestClient) -> None:
    import_seed(EXAMPLE_SEED)
    pid = _child_id(client)
    client.post(
        f"/person/{pid}/visit",
        data={"date": "2026-05-29", "specialty": "Хирург", "conclusion": "Здоров"},
        follow_redirects=False,
    )
    ev = _find_event(client, pid, "visit", "Хирург")
    vid = ev["ref_id"]
    client.post(
        f"/visit/{vid}",
        data={"date": "2026-05-29", "specialty": "Травматолог", "conclusion": "Ок"},
        follow_redirects=False,
    )
    assert _find_event(client, pid, "visit", "Травматолог")
    client.post(f"/visit/{vid}/delete", follow_redirects=False)
    kinds = [(e["kind"], e["title"]) for e in client.get(f"/api/person/{pid}/timeline").json()]
    assert ("visit", "Травматолог") not in kinds


def test_visit_with_inbox_scan(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTAL_DOCUMENTS_ROOT", str(tmp_path / "docs"))
    monkeypatch.setenv("PORTAL_DOCUMENTS_INBOX", str(tmp_path / "inbox"))
    get_settings.cache_clear()
    (tmp_path / "inbox").mkdir()
    (tmp_path / "inbox" / "scan_visit.pdf").write_bytes(b"%PDF-1.4 visit")

    import_seed(EXAMPLE_SEED)
    pid = _child_id(client)
    client.post(
        f"/person/{pid}/visit",
        data={"date": "2026-03-09", "specialty": "Травматолог-ортопед",
              "inbox_name": "scan_visit.pdf"},
        follow_redirects=False,
    )
    ev = _find_event(client, pid, "visit", "Травматолог-ортопед")
    assert ev["extra"]["document_path"] is not None
    assert not (tmp_path / "inbox" / "scan_visit.pdf").exists()
    resp = client.get(f"/visit-documents/{ev['ref_id']}")
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")

    get_settings.cache_clear()


def test_illness_crud(client: TestClient) -> None:
    import_seed(EXAMPLE_SEED)
    pid = _child_id(client)
    client.post(
        f"/person/{pid}/illness",
        data={"start_date": "2026-05-01", "title": "Простуда", "status": "resolved"},
        follow_redirects=False,
    )
    ev = _find_event(client, pid, "illness", "Простуда")
    iid = ev["ref_id"]
    client.post(
        f"/illness/{iid}",
        data={"start_date": "2026-05-01", "title": "Грипп", "status": "resolved"},
        follow_redirects=False,
    )
    assert _find_event(client, pid, "illness", "Грипп")
    client.post(f"/illness/{iid}/delete", follow_redirects=False)
    titles = [e["title"] for e in client.get(f"/api/person/{pid}/timeline").json()]
    assert "Грипп" not in titles
