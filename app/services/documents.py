"""Хранилище медицинских документов (сканов).

Два бэкенда, переключаются настройкой ``documents_backend``:

- ``local`` — файлы в каталоге ``documents_root`` (для разработки и локального запуска);
- ``smb``   — портал сам подключается к SMB-шаре (``smb_*`` в настройках),
  монтировать в ОС ничего не нужно.

Организация одинакова для обоих бэкендов:

    {Имя}/{YYYY-MM-DD}__{slug}__aid{analysis_id}.{ext}

- папка на каждого человека — для удобного просмотра прямо в шаре;
- токен ``aid{analysis_id}`` однозначно привязывает файл к записи анализа в БД;
- в БД (``analysis.document_path``) хранится путь относительно корня.
"""

import re
import unicodedata
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path

from app.config import get_settings

_SEP_RE = re.compile(r"[^\w\-]+", re.UNICODE)

# Расширения, считаемые документами (для списка «входящих»).
_DOC_EXTS = (".pdf", ".jpg", ".jpeg", ".png")


def _slug(value: str) -> str:
    """Безопасное имя файла/папки: разделители убираются, пунктуация → дефис.

    Юникод (кириллица) сохраняется — ext4/SMB его держат.
    """
    value = unicodedata.normalize("NFC", value).strip().lower()
    value = _SEP_RE.sub("-", value).strip("-")
    return value or "doc"


def _is_safe_relpath(relpath: str) -> bool:
    """Отклонить path-traversal: пустые сегменты, ``..`` и абсолютные пути."""
    if not relpath or relpath.startswith(("/", "\\")):
        return False
    parts = relpath.replace("\\", "/").split("/")
    return all(p not in ("", ".", "..") for p in parts)


def canonical_relpath(
    person_name: str,
    record_date: date,
    title: str,
    record_id: int,
    ext: str = ".pdf",
    id_prefix: str = "aid",
) -> str:
    """Построить канонический путь документа относительно корня хранилища.

    ``id_prefix`` отличает сущности в одной папке человека: ``aid`` — анализ,
    ``vid`` — визит (id-последовательности таблиц независимы, иначе был бы конфликт).
    """
    if not ext.startswith("."):
        ext = "." + ext
    folder = _slug(person_name)
    name = f"{record_date.isoformat()}__{_slug(title)}__{id_prefix}{record_id}{ext}"
    return f"{folder}/{name}"


class DocumentStore(ABC):
    """Бэкенд хранилища документов: чтение/запись по относительному пути."""

    def canonical_relpath(
        self,
        person_name: str,
        analysis_date: date,
        title: str,
        analysis_id: int,
        ext: str = ".pdf",
    ) -> str:
        return canonical_relpath(person_name, analysis_date, title, analysis_id, ext)

    @abstractmethod
    def read(self, relpath: str | None) -> bytes | None:
        """Прочитать файл; None, если путь небезопасен или файла нет."""

    @abstractmethod
    def write(self, relpath: str, data: bytes) -> None:
        """Записать файл (создав папки при необходимости)."""

    @abstractmethod
    def list_inbox(self) -> list[str]:
        """Имена неразобранных сканов во «входящих» (отсортированы)."""

    @abstractmethod
    def move_from_inbox(self, name: str, relpath: str) -> None:
        """Перенести файл из «входящих» в каноническое место под корнем."""


class LocalDocumentStore(DocumentStore):
    """Файлы в каталоге на диске (``documents_root``); «входящие» — ``inbox``."""

    def __init__(self, root: Path, inbox: Path) -> None:
        self._root = root
        self._inbox = inbox

    def read(self, relpath: str | None) -> bytes | None:
        if not relpath or not _is_safe_relpath(relpath):
            return None
        root = self._root.resolve()
        target = (root / relpath).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            return None
        return target.read_bytes()

    def write(self, relpath: str, data: bytes) -> None:
        if not _is_safe_relpath(relpath):
            raise ValueError(f"Небезопасный путь: {relpath}")
        target = (self._root.resolve() / relpath).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def list_inbox(self) -> list[str]:
        if not self._inbox.is_dir():
            return []
        names = [
            p.name
            for p in self._inbox.iterdir()
            if p.is_file() and p.suffix.lower() in _DOC_EXTS
        ]
        return sorted(names)

    def move_from_inbox(self, name: str, relpath: str) -> None:
        if "/" in name or "\\" in name or name in ("", ".", ".."):
            raise ValueError(f"Недопустимое имя файла: {name}")
        src = (self._inbox.resolve() / name).resolve()
        if not src.is_relative_to(self._inbox.resolve()) or not src.is_file():
            raise FileNotFoundError(f"Нет файла во входящих: {name}")
        self.write(relpath, src.read_bytes())
        src.unlink()


class SmbDocumentStore(DocumentStore):
    """Портал сам подключается к SMB-шаре (через smbprotocol), без монтирования."""

    def __init__(
        self, host: str, share: str, root: str, user: str, password: str
    ) -> None:
        self._host = host
        self._share = share
        self._root = root.strip("/\\")
        # Учётные данные по умолчанию для всех подключений к этому серверу.
        import smbclient

        smbclient.ClientConfig(username=user, password=password)
        self._smbclient = smbclient

    def _unc(self, relpath: str) -> str:
        segs = [s for s in [self._root, *relpath.replace("\\", "/").split("/")] if s]
        return rf"\\{self._host}\{self._share}" + "".join("\\" + s for s in segs)

    def read(self, relpath: str | None) -> bytes | None:
        if not relpath or not _is_safe_relpath(relpath):
            return None
        unc = self._unc(relpath)
        if not self._smbclient.path.exists(unc):
            return None
        with self._smbclient.open_file(unc, mode="rb") as f:
            return bytes(f.read())

    def write(self, relpath: str, data: bytes) -> None:
        if not _is_safe_relpath(relpath):
            raise ValueError(f"Небезопасный путь: {relpath}")
        unc = self._unc(relpath)
        parent = unc.rsplit("\\", 1)[0]
        self._smbclient.makedirs(parent, exist_ok=True)
        with self._smbclient.open_file(unc, mode="wb") as f:
            f.write(data)

    def _share_root(self) -> str:
        return rf"\\{self._host}\{self._share}"

    def list_inbox(self) -> list[str]:
        # «Входящие» — корень шары, минус подпапка документов и служебное.
        skip = {self._root.lower(), "lost+found"}
        names = []
        for n in self._smbclient.listdir(self._share_root()):
            if n.lower() in skip:
                continue
            ext = ("." + n.rsplit(".", 1)[-1]).lower() if "." in n else ""
            if ext in _DOC_EXTS:
                names.append(n)
        return sorted(names)

    def move_from_inbox(self, name: str, relpath: str) -> None:
        if "/" in name or "\\" in name or name in ("", ".", ".."):
            raise ValueError(f"Недопустимое имя файла: {name}")
        src = self._share_root() + "\\" + name
        if not self._smbclient.path.exists(src):
            raise FileNotFoundError(f"Нет файла во входящих: {name}")
        with self._smbclient.open_file(src, mode="rb") as f:
            data = bytes(f.read())
        self.write(relpath, data)
        self._smbclient.remove(src)


def build_document_store() -> DocumentStore:
    """Собрать бэкенд по настройкам (``documents_backend``)."""
    s = get_settings()
    if s.documents_backend == "smb":
        return SmbDocumentStore(
            s.smb_host, s.smb_share, s.smb_root, s.smb_user, s.smb_password
        )
    return LocalDocumentStore(s.documents_root, s.documents_inbox)
