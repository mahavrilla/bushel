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
