.PHONY: install run dev test lint format typecheck check import

install:        ## Установить зависимости (с dev-инструментами)
	pip install -e ".[dev]"

import:         ## Импортировать данные из пространства analizy
	python -m scripts.import_analizy

run:            ## Запустить сервер
	uvicorn app.main:app --host $${PORTAL_HOST:-127.0.0.1} --port $${PORTAL_PORT:-8000}

dev:            ## Запустить сервер с авто-перезагрузкой
	uvicorn app.main:app --reload

test:           ## Прогнать тесты
	pytest

lint:           ## Проверить стиль (ruff)
	ruff check .

format:         ## Отформатировать код (ruff)
	ruff format .

typecheck:      ## Проверить типы (mypy)
	mypy app

check: lint typecheck test  ## Полная проверка перед коммитом
