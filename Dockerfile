FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Set working directory
WORKDIR /app

# Copy dependency files and minimal package stub (hatchling needs __init__.py to build)
COPY pyproject.toml uv.lock* ./
RUN mkdir -p factfeed && touch factfeed/__init__.py

# Install dependencies (cached unless pyproject.toml/uv.lock change)
RUN uv sync --frozen --no-dev

# Download spaCy multilingual model (pip needed internally by spacy download)
RUN uv pip install pip && uv run python -m spacy download xx_sent_ud_sm

# Copy application code
COPY factfeed/ ./factfeed/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Default command (overridden in docker-compose.yml per service)
CMD ["uv", "run", "uvicorn", "factfeed.web.main:app", "--host", "0.0.0.0", "--port", "8000"]
