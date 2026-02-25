FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Set working directory
WORKDIR /app

# Copy dependency files and package source (hatchling needs the package to build)
COPY pyproject.toml uv.lock* ./
COPY factfeed/ ./factfeed/

# Install dependencies
RUN uv sync --frozen --no-dev

# Download spaCy English model (pip needed internally by spacy download)
RUN uv pip install pip && uv run python -m spacy download en_core_web_sm

# Copy application code
COPY factfeed/ ./factfeed/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Default command (overridden in docker-compose.yml per service)
CMD ["uv", "run", "uvicorn", "factfeed.web.main:app", "--host", "0.0.0.0", "--port", "8000"]
