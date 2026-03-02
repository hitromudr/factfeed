# Stage 1: Builder
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Create a dummy project structure to satisfy build backends (hatchling)
# ensuring the virtualenv is created with the project installed in editable mode
RUN mkdir -p factfeed && touch factfeed/__init__.py

# Install dependencies into /app/.venv
# --frozen: Sync exactly from uv.lock
# --no-dev: Exclude development dependencies
RUN uv sync --frozen --no-dev

# Download spaCy multilingual model
# We install pip explicitly because spacy download command uses it internally
RUN uv run python -m ensurepip && \
    uv run python -m pip install --upgrade pip && \
    uv run python -m spacy download xx_sent_ud_sm

# Stage 2: Runtime
FROM python:3.12-slim

# Copy uv (useful for runtime commands like 'uv run alembic', though venv is in PATH)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Add virtual environment to PATH
# This ensures 'python' and 'uvicorn' commands use the venv by default
ENV PATH="/app/.venv/bin:$PATH"

# Copy dependency files for uv runtime checks
COPY pyproject.toml uv.lock ./

# Copy application code
COPY factfeed/ ./factfeed/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Default command
# Note: we don't strictly need 'uv run' here since venv is in PATH,
# but keeping it provides consistency and explicit environment usage.
CMD ["uv", "run", "uvicorn", "factfeed.web.main:app", "--host", "0.0.0.0", "--port", "8000"]
