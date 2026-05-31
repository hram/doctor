from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация приложения. Значения берутся из переменных окружения
    (префикс ``PORTAL_``) или из файла ``.env``."""

    model_config = SettingsConfigDict(
        env_prefix="PORTAL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Семейный портал здоровья"
    debug: bool = False
    database_path: Path = Path("data/app.sqlite3")

    # --- Хранилище медицинских документов (сканов) ---
    # Бэкенд: "local" (файлы на диске) или "smb" (портал сам коннектится к шаре).
    documents_backend: str = "local"
    # local: корень-каталог с документами и каталог «входящих» (неразобранных сканов).
    documents_root: Path = Path("data/documents")
    documents_inbox: Path = Path("data/inbox")
    # smb: параметры подключения (портал подключается сам, монтировать не нужно).
    smb_host: str = ""          # напр. 192.168.1.72
    smb_share: str = ""         # напр. scans
    smb_root: str = ""          # подпапка внутри шары, напр. analizy
    smb_user: str = ""          # напр. family
    smb_password: str = ""      # пароль (в .env, не в репозитории)

    host: str = "127.0.0.1"
    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    """Кэшированный синглтон настроек.

    Используется как FastAPI-зависимость и при прямом доступе из слоёв.
    В тестах кэш сбрасывается через ``get_settings.cache_clear()``.
    """
    return Settings()
