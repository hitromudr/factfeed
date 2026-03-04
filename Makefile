.PHONY: help install dev test lint format clean \
        reset up start stop down restart logs ps shell db-shell \
        migrate revision init-test-db \
        i18n-extract i18n-update i18n-compile i18n-init

# Configuration
APP_MODULE := factfeed.web.main:app
HOST := 0.0.0.0
PORT := 8000
# Connect to Docker Postgres from host (port 5433)
LOCAL_DB_URL := postgresql+asyncpg://factfeed:factfeed@localhost:5433/factfeed
TEST_DB_URL := postgresql+asyncpg://factfeed:factfeed@localhost:5433/factfeed_test

help:
	@echo "FactFeed Project Management"
	@echo "==========================="
	@echo "Development (Local):"
	@echo "  make install       Install dependencies"
	@echo "  make dev           Start local server with hot reload"
	@echo "  make test          Run tests"
	@echo "  make lint          Run linters (ruff)"
	@echo "  make format        Format code (ruff)"
	@echo "  make clean         Cleanup cache files"
	@echo ""
	@echo "Docker Management:"
	@echo "  make reset         Clear database and restart pipeline"
	@echo "  make up            Start stack in foreground"
	@echo "  make start         Start stack in background (daemon)"
	@echo "  make stop          Stop stack"
	@echo "  make restart       Restart stack"
	@echo "  make down          Stop and remove containers"
	@echo "  make logs          Follow container logs"
	@echo "  make ps            Show container status"
	@echo "  make shell         Shell into app container"
	@echo ""
	@echo "Database:"
	@echo "  make migrate       Apply migrations"
	@echo "  make revision      Create new migration"
	@echo "  make db-shell      Connect to database (psql)"
	@echo ""
	@echo "i18n:"
	@echo "  make i18n-extract  Extract strings to .pot"
	@echo "  make i18n-update   Update .po files"
	@echo "  make i18n-compile  Compile .mo files"

# --- Development ---

install:
	uv sync

dev:
	DATABASE_URL=$(LOCAL_DB_URL) uv run uvicorn $(APP_MODULE) --host $(HOST) --port $(PORT) --reload

test: init-test-db
	DATABASE_URL=$(TEST_DB_URL) TEST_DATABASE_URL=$(TEST_DB_URL) uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff check --fix .
	uv run ruff format .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf .coverage htmlcov

# --- Docker Control ---

reset:
	docker-compose down -v
	docker-compose up -d --build

up:
	docker-compose up -d --build

start:
	docker-compose up -d --build

stop:
	docker-compose stop

restart:
	docker-compose restart

down:
	docker-compose down

logs:
	docker-compose logs -f

ps:
	docker-compose ps

shell:
	docker-compose exec app /bin/sh

# --- Database ---

migrate:
	DATABASE_URL=$(LOCAL_DB_URL) uv run alembic upgrade head

revision:
	@printf "Enter migration message: "; \
	read msg; \
	DATABASE_URL=$(LOCAL_DB_URL) uv run alembic revision --autogenerate -m "$$msg"

init-test-db:
	docker-compose exec -T postgres createdb -U factfeed factfeed_test || true

db-shell:
	docker-compose exec postgres psql -U factfeed -d factfeed

# --- i18n ---

i18n-extract:
	uv run pybabel extract -F babel.cfg -k _ -o messages.pot .

i18n-update:
	uv run pybabel update -i messages.pot -d factfeed/translations

i18n-compile:
	uv run pybabel compile -d factfeed/translations

i18n-init:
	@printf "Enter locale code (e.g. ru): "; \
	read lang; \
	uv run pybabel init -i messages.pot -d factfeed/translations -l $$lang
