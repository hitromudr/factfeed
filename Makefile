.PHONY: help install run test migrate revision clean docker-up docker-down i18n-extract i18n-update i18n-compile

# Configuration
APP_MODULE := factfeed.web.main:app
HOST := 0.0.0.0
PORT := 8000

help:
	@echo "FactFeed Project Management"
	@echo "==========================="
	@echo "Dev Commands:"
	@echo "  make install       Install dependencies using uv"
	@echo "  make run           Start local development server"
	@echo "  make test          Run tests"
	@echo "  make clean         Remove cache files"
	@echo ""
	@echo "Database:"
	@echo "  make migrate       Apply database migrations"
	@echo "  make revision      Create a new migration (interactive)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up     Start services via Docker Compose"
	@echo "  make docker-down   Stop Docker services"
	@echo ""
	@echo "Localization (i18n):"
	@echo "  make i18n-extract  Extract translation strings to .pot file"
	@echo "  make i18n-update   Update translation catalogs (.po) from .pot"
	@echo "  make i18n-compile  Compile translation files (.mo)"
	@echo "  make i18n-init     Initialize a new language (interactive)"

install:
	uv sync

run:
	uv run uvicorn $(APP_MODULE) --host $(HOST) --port $(PORT) --reload

test:
	uv run pytest

migrate:
	uv run alembic upgrade head

revision:
	@read -p "Enter migration message: " msg; \
	uv run alembic revision --autogenerate -m "$$msg"

docker-up:
	docker-compose up --build

docker-down:
	docker-compose down

i18n-extract:
	uv run pybabel extract -F babel.cfg -o factfeed/translations/messages.pot .

i18n-update:
	uv run pybabel update -i factfeed/translations/messages.pot -d factfeed/translations

i18n-compile:
	uv run pybabel compile -d factfeed/translations

i18n-init:
	@read -p "Enter locale code (e.g. 'es' for Spanish): " lang; \
	uv run pybabel init -i factfeed/translations/messages.pot -d factfeed/translations -l $$lang

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf .coverage htmlcov
