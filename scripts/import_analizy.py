"""CLI: импорт данных из пространства analizy в БД портала.

Запуск:
    python -m scripts.import_analizy [путь_к_seed.json]

Инициализирует схему БД (если нужно) и идемпотентно загружает seed. Путь к БД
берётся из настроек (PORTAL_DATABASE_PATH / .env).
"""

import sys
from pathlib import Path

from app.db.database import init_db
from app.ingestion.analizy import DEFAULT_SEED, EXAMPLE_SEED, import_seed


def main() -> None:
    seed_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SEED
    if not seed_path.exists():
        print(
            f"Не найден файл с данными: {seed_path}\n"
            f"Реальные данные семьи в репозиторий не коммитятся (см. .gitignore).\n"
            f"Положите свой {DEFAULT_SEED.name} рядом или запустите на примере:\n"
            f"    python -m scripts.import_analizy {EXAMPLE_SEED}"
        )
        raise SystemExit(1)
    init_db()
    stats = import_seed(seed_path)
    print(
        "Импорт из analizy завершён: "
        f"людей={stats.people}, анализов={stats.analyses}, "
        f"визитов={stats.visits}, болезней={stats.illnesses}, "
        f"связей={stats.relations}"
    )


if __name__ == "__main__":
    main()
