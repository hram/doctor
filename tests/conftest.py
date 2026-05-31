import sqlite3
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings


@pytest.fixture(autouse=True)
def _isolate_documents(tmp_path, monkeypatch) -> None:
    """Изолировать тесты от реального .env: локальный бэкенд + временные каталоги.

    Иначе настройки портала (например, .env с backend=smb) утекли бы в тесты.
    Тесты, которым нужны свои каталоги документов, переопределяют эти переменные.
    """
    monkeypatch.setenv("PORTAL_DOCUMENTS_BACKEND", "local")
    monkeypatch.setenv("PORTAL_DOCUMENTS_ROOT", str(tmp_path / "_docs"))
    monkeypatch.setenv("PORTAL_DOCUMENTS_INBOX", str(tmp_path / "_inbox"))
    get_settings.cache_clear()


@pytest.fixture
def client(monkeypatch) -> Iterator[TestClient]:
    """TestClient с изолированной in-memory БД на каждый тест.

    Используется shared-cache in-memory SQLite: база живёт, пока открыт
    ``anchor``-соединение, поэтому отдельные соединения репозитория видят
    одну и ту же БД. Уникальное имя на тест → полная изоляция. Диска и fsync
    нет — setup на порядок(и) быстрее файловой БД (см. CLAUDE.md → «Тесты»).
    """
    dsn = f"file:test_{uuid.uuid4().hex}?mode=memory&cache=shared"
    monkeypatch.setenv("PORTAL_DATABASE_PATH", dsn)
    get_settings.cache_clear()

    anchor = sqlite3.connect(dsn, uri=True)  # держит in-memory БД живой весь тест
    try:
        from app.main import create_app

        app = create_app()
        with TestClient(app) as test_client:  # триггерит lifespan → init_db()
            yield test_client
    finally:
        anchor.close()
        get_settings.cache_clear()
