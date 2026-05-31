import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.config import get_settings

# Схема БД. Для одного небольшого портала простых миграций «CREATE TABLE IF NOT
# EXISTS» достаточно; при росте проекта замените на полноценный мигратор.
#
# Ядро спроектировано источник-независимым: ручной ввод, импорт из analizy и
# будущий SMClinic-синк пишут в одни и те же таблицы. Колонка ``source`` хранит
# происхождение записи, ``source_ref`` — внешний идентификатор источника.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS person (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL UNIQUE,
    full_name  TEXT,
    birth_date TEXT,
    role       TEXT    NOT NULL DEFAULT 'child',  -- parent | child
    sex        TEXT,                              -- male | female | null
    notes      TEXT,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Семейный граф. kind описывает роль person_id относительно relative_id.
CREATE TABLE IF NOT EXISTS relation (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id   INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    relative_id INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    kind        TEXT    NOT NULL,  -- parent_of | child_of | sibling_of
    UNIQUE (person_id, relative_id, kind)
);

-- Справочник показателей (марок). Референс по умолчанию; конкретное измерение
-- может переопределить диапазон значениями ref_low/ref_high в measurement.
CREATE TABLE IF NOT EXISTS marker (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    code     TEXT    NOT NULL UNIQUE,
    name     TEXT    NOT NULL,
    unit     TEXT,
    ref_low  REAL,
    ref_high REAL
);

-- Событие сдачи анализа / медицинский документ.
CREATE TABLE IF NOT EXISTS analysis (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id     INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    date          TEXT    NOT NULL,            -- YYYY-MM-DD
    category      TEXT,                        -- кровь | биохимия | кал | пцр | узи | ...
    title         TEXT    NOT NULL,
    lab           TEXT,
    source        TEXT    NOT NULL DEFAULT 'manual',
    source_ref    TEXT,
    document_path TEXT,
    notes         TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (person_id, date, title)
);

-- Значение показателя. value_num — для количественных (графики),
-- value_text — для качественных («обнаружено», «2-4»).
CREATE TABLE IF NOT EXISTS measurement (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL REFERENCES analysis(id) ON DELETE CASCADE,
    marker_id   INTEGER REFERENCES marker(id),
    value_num   REAL,
    value_text  TEXT,
    unit        TEXT,
    ref_low     REAL,
    ref_high    REAL,
    flag        TEXT,  -- normal | high | low | positive | negative
    UNIQUE (analysis_id, marker_id)
);

-- Эпизод болезни.
CREATE TABLE IF NOT EXISTS illness (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id  INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    start_date TEXT    NOT NULL,
    end_date   TEXT,
    title      TEXT    NOT NULL,
    status     TEXT,   -- active | resolved | ...
    notes      TEXT,
    UNIQUE (person_id, start_date, title)
);

-- Визит к врачу (прошедший).
CREATE TABLE IF NOT EXISTS visit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id   INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    date        TEXT    NOT NULL,
    doctor_name TEXT,
    specialty   TEXT,
    clinic      TEXT,
    conclusion  TEXT,
    notes       TEXT,
    source      TEXT    NOT NULL DEFAULT 'manual',
    document_path TEXT,
    UNIQUE (person_id, date, specialty, doctor_name)
);

-- Рекомендация / контрольная точка (может быть привязана к визиту).
CREATE TABLE IF NOT EXISTS recommendation (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    visit_id  INTEGER REFERENCES visit(id) ON DELETE SET NULL,
    text      TEXT    NOT NULL,
    kind      TEXT,   -- medication | control | referral | lifestyle
    due_date  TEXT,
    status    TEXT    NOT NULL DEFAULT 'open',  -- open | done
    UNIQUE (person_id, text, visit_id)
);

-- Планируемый визит.
CREATE TABLE IF NOT EXISTS appointment (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id         INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    planned_date      TEXT,
    specialty         TEXT,
    reason            TEXT,
    status            TEXT    NOT NULL DEFAULT 'planned',  -- planned | done | cancelled
    recommendation_id INTEGER REFERENCES recommendation(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_analysis_person       ON analysis(person_id, date);
CREATE INDEX IF NOT EXISTS idx_measurement_analysis  ON measurement(analysis_id);
CREATE INDEX IF NOT EXISTS idx_visit_person          ON visit(person_id, date);
CREATE INDEX IF NOT EXISTS idx_illness_person        ON illness(person_id, start_date);
CREATE INDEX IF NOT EXISTS idx_recommendation_person ON recommendation(person_id);
"""

# Справочник показателей. Сидируется при инициализации БД (idempotent — INSERT OR
# IGNORE по уникальному code). Референсы — ориентировочные, конкретный бланк может
# давать свой диапазон, который пишется в measurement.ref_low/ref_high.
_MARKERS_SEED: tuple[tuple[str, str, str | None, float | None, float | None], ...] = (
    ("aslo", "АСЛО", "Ед/мл", 0.0, 200.0),
    ("iron", "Железо", "мкмоль/л", 7.2, 21.5),
    ("ferritin", "Ферритин", "нг/мл", 6.0, 320.0),
    ("vitamin_d", "Витамин D (25-OH)", "нг/мл", 30.0, 100.0),
    ("zinc", "Цинк", "мкг/мл", 0.78, 1.18),
    ("glucose", "Глюкоза", "ммоль/л", 3.3, 5.5),
    ("chloride", "Хлор", "ммоль/л", 98.0, 107.0),
    ("phosphorus", "Фосфор", "ммоль/л", 1.0, 1.8),
    ("folate", "Фолиевая кислота", "нг/мл", 3.0, 17.0),
    ("b12", "Витамин B12", "пг/мл", 187.0, 883.0),
    ("ige", "Иммуноглобулин E", "МЕ/мл", 0.0, 90.0),
    # Общий анализ крови (ОАК) + лейкоформула. Референсы возрастные и зависят от
    # лаборатории, поэтому в справочнике не фиксируются (None) — конкретный
    # диапазон пишется в measurement.ref_low/ref_high из бланка.
    ("wbc", "Лейкоциты (WBC)", "10⁹/л", None, None),
    ("rbc", "Эритроциты (RBC)", "10¹²/л", None, None),
    ("hgb", "Гемоглобин (Hb)", "г/л", None, None),
    ("hct", "Гематокрит (HCT)", "%", None, None),
    ("mcv", "MCV (средний объём эритроцита)", "фл", None, None),
    ("mch", "MCH (среднее содержание Hb)", "пг", None, None),
    ("mchc", "MCHC (средняя концентрация Hb)", "г/л", None, None),
    ("rdw", "RDW (ширина распределения эритроцитов)", "%", None, None),
    ("plt", "Тромбоциты (PLT)", "10⁹/л", None, None),
    ("mpv", "MPV (средний объём тромбоцита)", "фл", None, None),
    ("baso_pct", "Базофилы, %", "%", None, None),
    ("baso_abs", "Базофилы, абс.", "10⁹/л", None, None),
    ("neut_pct", "Нейтрофилы, %", "%", None, None),
    ("neut_abs", "Нейтрофилы, абс.", "10⁹/л", None, None),
    ("eos_pct", "Эозинофилы, %", "%", None, None),
    ("eos_abs", "Эозинофилы, абс.", "10⁹/л", None, None),
    ("mono_pct", "Моноциты, %", "%", None, None),
    ("mono_abs", "Моноциты, абс.", "10⁹/л", None, None),
    ("lymph_pct", "Лимфоциты, %", "%", None, None),
    ("lymph_abs", "Лимфоциты, абс.", "10⁹/л", None, None),
    ("esr", "СОЭ", "мм/ч", None, None),
    # Качественные/нечисловые показатели — без референса, значение в value_text.
    ("strep_pyogenes_pcr", "ПЦР Streptococcus pyogenes", None, None, None),
    ("lamblia", "Лямблиоз (ИГХ)", None, None, None),
    ("throat_culture", "Посев из зева", None, None, None),
)


def _open() -> sqlite3.Connection:
    """Открыть соединение по пути из настроек.

    Поддерживает два режима (выбираются значением ``PORTAL_DATABASE_PATH``):
    - обычный файл — для прод/локального запуска (durability сохраняется);
    - in-memory (``:memory:`` или URI ``file:...?mode=memory&cache=shared``) —
      для тестов: без диска и без fsync, отдельные соединения видят одну БД,
      пока живо хотя бы одно из них (anchor держит фикстура).
    """
    raw = str(get_settings().database_path)
    if raw == ":memory:" or raw.startswith("file:"):
        dsn = "file:portal?mode=memory&cache=shared" if raw == ":memory:" else raw
        conn = sqlite3.connect(dsn, uri=True)
    else:
        Path(raw).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(raw)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Открыть соединение с БД. Коммитит при успешном выходе, всегда закрывает.

    Путь к БД читается из настроек на каждый вызов — это позволяет тестам
    подменять базу через переменную окружения.
    """
    conn = _open()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _seed_markers(conn: sqlite3.Connection) -> None:
    """Засидить справочник показателей. Идемпотентно: INSERT OR IGNORE по code."""
    conn.executemany(
        "INSERT OR IGNORE INTO marker (code, name, unit, ref_low, ref_high) "
        "VALUES (?, ?, ?, ?, ?)",
        _MARKERS_SEED,
    )


def _migrate(conn: sqlite3.Connection) -> None:
    """Лёгкие миграции для уже существующих БД (CREATE TABLE IF NOT EXISTS не правит
    существующие таблицы). Идемпотентно: добавляем недостающие колонки."""
    visit_cols = {row[1] for row in conn.execute("PRAGMA table_info(visit)")}
    if "document_path" not in visit_cols:
        conn.execute("ALTER TABLE visit ADD COLUMN document_path TEXT")


def init_db() -> None:
    """Создать таблицы и засидить справочники. Вызывается на старте приложения."""
    with get_connection() as conn:
        conn.executescript(_SCHEMA)
        _migrate(conn)
        _seed_markers(conn)
