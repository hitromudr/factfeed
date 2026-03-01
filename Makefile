.PHONY: help install run test migrate revision clean docker-up docker-down i18n-extract i18n-update i18n-compile i18n-init

# Configuration
APP_MODULE := factfeed.web.main:app
HOST := 0.0.0.0
PORT := 8001
# Connect to Docker Postgres from host (port 5433)
LOCAL_DB_URL := postgresql+asyncpg://factfeed:factfeed@localhost:5433/factfeed
TEST_DB_URL := postgresql+asyncpg://factfeed:factfeed@localhost:5433/factfeed_test

help:
	@echo "FactFeed Project Management"
	@echo "==========================="
	@echo "Dev Commands:"
	@echo "  make install       Install dependencies"
	@echo "  make run           Start local server (uses docker db on port 5433)"
	@echo "  make test          Run tests"
	@echo "  make clean         Cleanup"
	@echo ""
	@echo "DB / Docker:"
	@echo "  make migrate       Apply migrations"
	@echo "  make revision      Create migration"
	@echo "  make init-test-db  Create test database in Docker"
	@echo "  make docker-up     Start full stack in Docker"
	@echo "  make docker-down   Stop Docker"
	@echo ""
	@echo "i18n:"
	@echo "  make i18n-extract  Extract strings"
	@echo "  make i18n-update   Update .po"
	@echo "  make i18n-compile  Compile .mo"
	@echo "  make i18n-init     Init new language"

install:
	uv sync
	uv pip install https://github.com/explosion/spacy-models/releases/download/xx_sent_ud_sm-3.8.0/xx_sent_ud_sm-3.8.0.tar.gz

run:
	DATABASE_URL=$(LOCAL_DB_URL) uv run uvicorn $(APP_MODULE) --host $(HOST) --port $(PORT) --reload

test:
	TEST_DATABASE_URL=$(TEST_DB_URL) uv run pytest

init-test-db:
	docker-compose exec -T postgres createdb -U factfeed factfeed_test || true

migrate:
	DATABASE_URL=$(LOCAL_DB_URL) uv run alembic upgrade head

revision:
	@printf "Enter migration message: "; \
	read msg; \
	DATABASE_URL=$(LOCAL_DB_URL) uv run alembic revision --autogenerate -m "$$msg"

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
	@printf "Enter locale code: "; \
	read lang; \
	uv run pybabel init -i factfeed/translations/messages.pot -d factfeed/translations -l $$lang

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf .coverage htmlcov
