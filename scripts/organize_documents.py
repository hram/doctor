"""CLI: привязать скан к анализу и разложить по правилу хранилища.

Запуск:
    python -m scripts.organize_documents <analysis_id> <путь_к_файлу>

Что делает:
1. Находит анализ и его владельца в БД.
2. Строит канонический путь
   ``{Имя}/{YYYY-MM-DD}__{slug}__aid{analysis_id}.{ext}`` под documents_root.
3. Копирует файл туда (создавая папку человека) и прописывает analysis.document_path.

Путь к хранилищу — из настроек (PORTAL_DOCUMENTS_ROOT / .env). После этого документ
виден в карточке человека по ссылке «📄 исходный документ».
"""

import sys
from pathlib import Path

from app.repositories.people import PersonRepository
from app.services.analyses import AnalysisService
from app.services.documents import build_document_store


def main() -> None:
    if len(sys.argv) != 3:
        print("Использование: python -m scripts.organize_documents <analysis_id> <файл>")
        raise SystemExit(2)

    analysis_id = int(sys.argv[1])
    source = Path(sys.argv[2])
    if not source.is_file():
        print(f"Файл не найден: {source}")
        raise SystemExit(1)

    analyses = AnalysisService()
    analysis = analyses.get(analysis_id)
    if analysis is None:
        print(f"Анализ с id={analysis_id} не найден в БД")
        raise SystemExit(1)

    person = PersonRepository().get(analysis.person_id)
    if person is None:
        print(f"Не найден человек person_id={analysis.person_id}")
        raise SystemExit(1)

    store = build_document_store()
    relpath = store.canonical_relpath(
        person.name, analysis.date, analysis.title, analysis.id, source.suffix or ".pdf"
    )
    store.write(relpath, source.read_bytes())
    analyses.set_document_path(analysis.id, relpath)

    print(f"Документ привязан к анализу id={analysis.id} ({person.name}, {analysis.date})")
    print(f"  document_path = {relpath}")


if __name__ == "__main__":
    main()
