# Bushel Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Bushel skeleton — a Dockerized FastAPI + Postgres + React app with the full database schema, migrations, health endpoints, and green test suites on both backend and frontend.

**Architecture:** API-first monorepo. `backend/` is a FastAPI service with SQLAlchemy 2.0 models and Alembic migrations against Postgres. `frontend/` is a Vite + React + TypeScript app that calls the backend over HTTP. `docker compose up` runs all three (db, api, web). This phase builds no business logic — it makes the scaffold real, runnable, and tested so later phases drop into a working chassis.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, psycopg 3, pydantic-settings, uv (Python packaging), pytest + httpx (backend tests); Vite, React 18, TypeScript, Vitest + Testing Library (frontend tests); Postgres 16; Docker Compose.

---

## File Structure

```
bushel/
├── docker-compose.yml                  # db + api + web
├── .env.example                        # documented env vars
├── README.md                           # how to run
├── backend/
│   ├── pyproject.toml                  # deps + tool config (uv)
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── migrations/
│   │   ├── env.py                      # Alembic runtime (reads settings)
│   │   └── versions/                   # generated migration(s)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI app + health route
│   │   ├── config.py                   # Settings (pydantic-settings)
│   │   ├── db.py                       # engine, SessionLocal, Base, get_db
│   │   └── models.py                   # all SQLAlchemy ORM models
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py                 # db fixtures, test client
│       ├── test_health.py
│       └── test_models.py
└── frontend/
    ├── package.json
    ├── Dockerfile
    ├── nginx.conf
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── api.ts                      # backend fetch helper
        └── App.test.tsx
```

**Responsibilities:**
- `app/config.py` — single source of configuration, read from env. Nothing else reads `os.environ`.
- `app/db.py` — owns the SQLAlchemy engine, session factory, declarative `Base`, and the `get_db` FastAPI dependency. Nothing else constructs engines.
- `app/models.py` — all ORM models (the schema hub). Imported by Alembic and by feature modules in later phases.
- `app/main.py` — app assembly + health endpoint only. Routers from later phases register here.
- `frontend/src/api.ts` — the only place that knows the backend base URL.

---

## Task 1: Backend project scaffold + health endpoint

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_health.py`

- [ ] **Step 1: Create `backend/pyproject.toml`**

```toml
[project]
name = "bushel-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.30",
    "sqlalchemy>=2.0",
    "psycopg[binary]>=3.1",
    "alembic>=1.13",
    "pydantic-settings>=2.2",
]

[dependency-groups]
dev = [
    "pytest>=8.2",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

- [ ] **Step 2: Create empty `backend/app/__init__.py` and `backend/tests/__init__.py`**

Both files are empty (package markers).

- [ ] **Step 3: Write the failing test** in `backend/tests/test_health.py`

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 4: Create minimal `backend/tests/conftest.py`** (empty for now; fixtures added in Task 5)

```python
# Shared pytest fixtures. Database fixtures are added in Task 5.
```

- [ ] **Step 5: Run the test to verify it fails**

Run (from `backend/`): `uv run pytest tests/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'` (or import error).

- [ ] **Step 6: Write minimal `backend/app/main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="Bushel API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 7: Run the test to verify it passes**

Run (from `backend/`): `uv run pytest tests/test_health.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/pyproject.toml backend/app backend/tests
git commit -m "feat(backend): scaffold FastAPI app with health endpoint"
```

---

## Task 2: Configuration via pydantic-settings

**Files:**
- Create: `backend/app/config.py`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_config.py`

```python
from app.config import Settings


def test_settings_reads_database_url_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/bushel")
    settings = Settings()
    assert settings.database_url == "postgresql+psycopg://u:p@localhost:5432/bushel"


def test_settings_has_kroger_and_llm_fields(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/bushel")
    monkeypatch.setenv("KROGER_CLIENT_ID", "cid")
    monkeypatch.setenv("KROGER_CLIENT_SECRET", "secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
    settings = Settings()
    assert settings.kroger_client_id == "cid"
    assert settings.kroger_client_secret == "secret"
    assert settings.anthropic_api_key == "sk-ant"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 3: Write `backend/app/config.py`**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str

    # Populated in later phases; optional so the app boots without them.
    kroger_client_id: str = ""
    kroger_client_secret: str = ""
    kroger_redirect_uri: str = "http://localhost:8000/auth/callback"
    anthropic_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat(backend): add typed settings via pydantic-settings"
```

---

## Task 3: Database engine, session, and Base

**Files:**
- Create: `backend/app/db.py`
- Test: `backend/tests/test_db.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_db.py`

```python
from sqlalchemy import text

from app.db import Base, engine


def test_base_has_metadata():
    assert Base.metadata is not None


def test_engine_connects():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.db'`.
(Note: this test requires a reachable Postgres. See Task 10 for `docker compose up db`; locally export `DATABASE_URL` to a running Postgres before running.)

- [ ] **Step 3: Write `backend/app/db.py`**

```python
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: Run the test to verify it passes**

Ensure Postgres is reachable and `DATABASE_URL` is set (e.g. `export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5432/bushel` with `docker compose up -d db`).
Run: `uv run pytest tests/test_db.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/db.py backend/tests/test_db.py
git commit -m "feat(backend): add SQLAlchemy engine, session, and Base"
```

---

## Task 4: ORM models for the full schema

Implements every table from the design spec. Postgres-specific `ARRAY` types are used for `aliases`, `source_recipe_ids`, and `scopes`.

**Files:**
- Create: `backend/app/models.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_models.py`

```python
from app.models import (
    GroceryList,
    GroceryListItem,
    Ingredient,
    IngredientProductMap,
    KrogerAuth,
    PurchaseLog,
    Recipe,
    RecipeIngredient,
)


def test_all_models_have_tablenames():
    expected = {
        Recipe: "recipes",
        RecipeIngredient: "recipe_ingredients",
        Ingredient: "ingredients",
        IngredientProductMap: "ingredient_product_map",
        GroceryList: "grocery_lists",
        GroceryListItem: "grocery_list_items",
        PurchaseLog: "purchase_log",
        KrogerAuth: "kroger_auth",
    }
    for model, table in expected.items():
        assert model.__tablename__ == table


def test_ingredient_has_canonical_name_and_aliases():
    cols = Ingredient.__table__.columns
    assert "canonical_name" in cols
    assert "aliases" in cols


def test_grocery_list_item_tracks_total_and_purchase_qty():
    cols = GroceryListItem.__table__.columns
    assert "total_qty" in cols
    assert "purchase_qty" in cols
    assert "pantry_status" in cols
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models'`.

- [ ] **Step 3: Write `backend/app/models.py`**

```python
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_servings: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(255), unique=True)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_purchase_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"))
    raw_text: Mapped[str] = mapped_column(Text)
    qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ingredient_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingredients.id", ondelete="SET NULL"), nullable=True
    )
    parse_source: Mapped[str] = mapped_column(String(20), default="library")


class IngredientProductMap(Base):
    __tablename__ = "ingredient_product_map"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id", ondelete="CASCADE"))
    kroger_upc: Mapped[str] = mapped_column(String(50))
    kroger_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    package_size: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)
    last_confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class GroceryList(Base):
    __tablename__ = "grocery_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    store_location_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GroceryListItem(Base):
    __tablename__ = "grocery_list_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("grocery_lists.id", ondelete="CASCADE"))
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id", ondelete="CASCADE"))
    total_qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    purchase_qty: Mapped[int] = mapped_column(Integer, default=1)
    kroger_upc: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_recipe_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    pantry_status: Mapped[str] = mapped_column(String(20), default="needed")


class PurchaseLog(Base):
    __tablename__ = "purchase_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id", ondelete="CASCADE"))
    kroger_upc: Mapped[str | None] = mapped_column(String(50), nullable=True)
    qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    purchased_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    source_list_id: Mapped[int | None] = mapped_column(
        ForeignKey("grocery_lists.id", ondelete="SET NULL"), nullable=True
    )


class KrogerAuth(Base):
    __tablename__ = "kroger_auth"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_models.py
git commit -m "feat(backend): add ORM models for full Bushel schema"
```

---

## Task 5: Database test fixtures + round-trip test

Adds fixtures that create all tables in a clean test database and provide a session, then proves a row round-trips.

**Files:**
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_models.py` (append)

- [ ] **Step 1: Replace `backend/tests/conftest.py` with database fixtures**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import Base

# Import models so they register on Base.metadata.
import app.models  # noqa: F401


@pytest.fixture(scope="session")
def test_engine():
    """Engine pointed at the configured database. Creates all tables once."""
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(test_engine):
    """A session wrapped in a transaction that is rolled back after each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
```

- [ ] **Step 2: Append the failing round-trip test** to `backend/tests/test_models.py`

```python
from app.models import Ingredient as _Ingredient


def test_ingredient_round_trips(db_session):
    ing = _Ingredient(canonical_name="all-purpose flour", aliases=["AP flour", "plain flour"])
    db_session.add(ing)
    db_session.flush()

    fetched = db_session.get(_Ingredient, ing.id)
    assert fetched is not None
    assert fetched.canonical_name == "all-purpose flour"
    assert "AP flour" in fetched.aliases
```

- [ ] **Step 3: Run the test to verify it fails or passes for the right reason**

Ensure a clean test DB is reachable (e.g. create database `bushel_test` and set `DATABASE_URL` to it: `export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5432/bushel_test`).
Run: `uv run pytest tests/test_models.py::test_ingredient_round_trips -v`
Expected: PASS (tables created by the fixture, row round-trips).

- [ ] **Step 4: Run the full backend suite**

Run: `uv run pytest -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/conftest.py backend/tests/test_models.py
git commit -m "test(backend): add db fixtures and model round-trip test"
```

---

## Task 6: Alembic migrations wired to models

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/versions/` (directory; migration generated in Step 4)

- [ ] **Step 1: Create `backend/alembic.ini`**

```ini
[alembic]
script_location = migrations
prepend_sys_path = .

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: Create `backend/migrations/env.py`**

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.db import Base
import app.models  # noqa: F401  (register tables on metadata)

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: Create the empty versions directory**

Run (from `backend/`): `mkdir -p migrations/versions`

- [ ] **Step 4: Generate the initial migration**

Ensure `DATABASE_URL` points at a reachable, empty database.
Run (from `backend/`): `uv run alembic revision --autogenerate -m "initial schema"`
Expected: a new file appears in `migrations/versions/` containing `create_table` calls for all eight tables.

- [ ] **Step 5: Apply and verify the migration**

Run: `uv run alembic upgrade head`
Expected: completes without error.
Verify: `uv run alembic current` shows the revision applied.

- [ ] **Step 6: Verify the migration is reversible**

Run: `uv run alembic downgrade base` then `uv run alembic upgrade head`
Expected: both succeed (round-trips cleanly).

- [ ] **Step 7: Commit**

```bash
git add backend/alembic.ini backend/migrations
git commit -m "feat(backend): add Alembic migrations for initial schema"
```

---

## Task 7: Backend Dockerfile

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/.dockerignore`

- [ ] **Step 1: Create `backend/.dockerignore`**

```
.venv
__pycache__
*.pyc
tests
.pytest_cache
```

- [ ] **Step 2: Create `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim

# Install uv (fast Python package manager).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first for layer caching.
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

# Copy the application.
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

EXPOSE 8000

# Apply migrations, then start the API.
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

- [ ] **Step 3: Build the image to verify it compiles**

Run (from `backend/`): `docker build -t bushel-api .`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add backend/Dockerfile backend/.dockerignore
git commit -m "feat(backend): add Dockerfile"
```

---

## Task 8: Frontend scaffold + health page with test

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/api.ts`
- Create: `frontend/src/App.tsx`
- Test: `frontend/src/App.test.tsx`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "bushel-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.6",
    "@testing-library/react": "^16.0.0",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "jsdom": "^24.1.0",
    "typescript": "^5.5.3",
    "vite": "^5.3.3",
    "vitest": "^2.0.3"
  }
}
```

- [ ] **Step 2: Create `frontend/vite.config.ts`**

```typescript
/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 5173 },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["@testing-library/jest-dom/vitest"],
  },
});
```

- [ ] **Step 3: Create `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Bushel</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 4: Create `frontend/src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";

import { App } from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 5: Create `frontend/src/api.ts`**

```typescript
const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function getHealth(): Promise<{ status: string }> {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json();
}
```

- [ ] **Step 6: Write the failing test** in `frontend/src/App.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

describe("App", () => {
  it("renders the Bushel title", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /bushel/i })).toBeInTheDocument();
  });

  it("shows backend status once health resolves", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );
    render(<App />);
    expect(await screen.findByText(/backend: ok/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 7: Run the test to verify it fails**

Run (from `frontend/`): `npm install` then `npm test`
Expected: FAIL — `App` cannot be found / no such file.

- [ ] **Step 8: Write `frontend/src/App.tsx`**

```tsx
import { useEffect, useState } from "react";

import { getHealth } from "./api";

export function App() {
  const [status, setStatus] = useState<string>("…");

  useEffect(() => {
    getHealth()
      .then((h) => setStatus(h.status))
      .catch(() => setStatus("unreachable"));
  }, []);

  return (
    <main>
      <h1>Bushel</h1>
      <p>Backend: {status}</p>
    </main>
  );
}
```

- [ ] **Step 9: Run the test to verify it passes**

Run (from `frontend/`): `npm test`
Expected: both tests PASS.

- [ ] **Step 10: Commit**

```bash
git add frontend/package.json frontend/vite.config.ts frontend/index.html frontend/src
git commit -m "feat(frontend): scaffold React app with health status page"
```

---

## Task 9: Frontend Dockerfile + nginx

**Files:**
- Create: `frontend/nginx.conf`
- Create: `frontend/Dockerfile`
- Create: `frontend/.dockerignore`

- [ ] **Step 1: Create `frontend/.dockerignore`**

```
node_modules
dist
```

- [ ] **Step 2: Create `frontend/nginx.conf`**

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 3: Create `frontend/Dockerfile`**

```dockerfile
FROM node:20-slim AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
```

- [ ] **Step 4: Build the image to verify it compiles**

Run (from `frontend/`): `docker build -t bushel-web .`
Expected: build succeeds (TypeScript compiles, Vite builds).

- [ ] **Step 5: Commit**

```bash
git add frontend/Dockerfile frontend/.dockerignore frontend/nginx.conf
git commit -m "feat(frontend): add Dockerfile and nginx config"
```

---

## Task 10: Docker Compose + environment template

**Files:**
- Create: `docker-compose.yml` (repo root)
- Create: `.env.example` (repo root)

- [ ] **Step 1: Create `.env.example`**

```bash
# Postgres
POSTGRES_USER=bushel
POSTGRES_PASSWORD=bushel
POSTGRES_DB=bushel

# Backend (note: host is the compose service name "db")
DATABASE_URL=postgresql+psycopg://bushel:bushel@db:5432/bushel

# Kroger Public API (fill in from developer.kroger.com; used in Phase 4)
KROGER_CLIENT_ID=
KROGER_CLIENT_SECRET=
KROGER_REDIRECT_URI=http://localhost:8000/auth/callback

# Anthropic (Claude) — used for recipe/ingredient parsing in Phase 2
ANTHROPIC_API_KEY=

# Frontend
VITE_API_URL=http://localhost:8000
```

- [ ] **Step 2: Create `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "5432:5432"
    volumes:
      - bushel_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 3s
      retries: 10

  api:
    build: ./backend
    environment:
      DATABASE_URL: ${DATABASE_URL}
      KROGER_CLIENT_ID: ${KROGER_CLIENT_ID}
      KROGER_CLIENT_SECRET: ${KROGER_CLIENT_SECRET}
      KROGER_REDIRECT_URI: ${KROGER_REDIRECT_URI}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy

  web:
    build: ./frontend
    ports:
      - "5173:80"
    depends_on:
      - api

volumes:
  bushel_pgdata:
```

- [ ] **Step 3: Bring the stack up**

Run (from repo root): `cp .env.example .env && docker compose up --build -d`
Expected: all three services start; `db` becomes healthy; `api` runs migrations on boot.

- [ ] **Step 4: Verify the backend health endpoint through the running container**

Run: `curl -s http://localhost:8000/health`
Expected: `{"status":"ok"}`

- [ ] **Step 5: Verify the frontend serves and reaches the backend**

Open `http://localhost:5173` in a browser.
Expected: page shows "Bushel" and "Backend: ok".

- [ ] **Step 6: Verify migrations created the tables**

Run: `docker compose exec db psql -U bushel -d bushel -c "\dt"`
Expected: all eight tables listed (recipes, recipe_ingredients, ingredients, ingredient_product_map, grocery_lists, grocery_list_items, purchase_log, kroger_auth) plus `alembic_version`.

- [ ] **Step 7: Tear down**

Run: `docker compose down`
Expected: services stop cleanly (data persists in the `bushel_pgdata` volume).

- [ ] **Step 8: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "feat: add Docker Compose stack and env template"
```

---

## Task 11: Top-level README

**Files:**
- Create: `README.md` (repo root)

- [ ] **Step 1: Create `README.md`**

````markdown
# Bushel

Personal grocery-planning app: turn recipes into a consolidated grocery list and push it to a
Kroger cart, with self-tracked purchase history powering "do you still have it?" prompts.

See the design spec in `docs/superpowers/specs/` and implementation plans in
`docs/superpowers/plans/`.

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000 (health at `/health`)

## Backend development

```bash
cd backend
uv sync
export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5432/bushel
uv run pytest          # run tests (requires a reachable Postgres)
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## Frontend development

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173
npm test
```

## Architecture

API-first: FastAPI backend + React frontend + Postgres, all via Docker Compose. The backend is
split into focused modules; fuzzy logic (parsing, matching, pantry guesses) is isolated from
deterministic logic (consolidation math, Kroger calls). A future iOS client reuses the same API.
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add top-level README"
```

---

## Self-Review

**Spec coverage (Phase 1 scope only):** This plan covers the foundation slice — Docker Compose
(db/api/web), Postgres, the **full** schema from the spec's data-model section (all eight tables),
Alembic migrations, health endpoints, and test harnesses on both ends. Business-logic modules
(`recipes/`, `ingredients/`, `consolidate/`, `pantry/`, `matching/`, `kroger/`, `llm/`) are
intentionally **out of scope** for Phase 1 and handled in Phases 2–6. The `config.py` already
declares Kroger and Anthropic settings so later phases need no rework there.

**Placeholder scan:** No TBD/TODO/"add error handling" placeholders. Every code step contains
complete, runnable content. Empty-file steps (package markers, versions dir) are explicitly noted
as intentionally empty.

**Type/name consistency:** Model class names and `__tablename__` values used in `models.py`,
`test_models.py`, and the migration match the spec's data model exactly. `DATABASE_URL` uses the
`postgresql+psycopg://` driver prefix consistently across config, tests, `.env.example`, and
README. `get_settings()` is the single settings accessor used by `db.py` and `migrations/env.py`.
Frontend `getHealth()` and the `App` component names are consistent across `api.ts`, `App.tsx`,
and `App.test.tsx`.

**Note on DB-dependent tests:** Tasks 3 and 5 require a reachable Postgres; each step states how to
provide one (`docker compose up -d db` plus an exported `DATABASE_URL`). This is called out so the
implementing engineer isn't surprised by connection errors.
```
