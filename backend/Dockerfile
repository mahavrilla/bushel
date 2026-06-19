FROM python:3.12-slim

# Install uv (fast Python package manager).
COPY --from=ghcr.io/astral-sh/uv:0.11.23 /uv /uvx /bin/

WORKDIR /app

# Install dependencies first for layer caching.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy the application.
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

EXPOSE 8000

# Apply migrations, then start the API.
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
