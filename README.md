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
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

### Running tests safely

> ⚠️ **The test fixture (`tests/conftest.py`) runs `Base.metadata.drop_all()` on teardown
> against whatever `DATABASE_URL` points at.** Never run the suite against the dev database —
> it will wipe your data. Always point tests at a throwaway database on a different port:

```bash
# one-time: a disposable test Postgres on 5544 (separate from the dev DB on 5432)
docker run -d --name bushel-test-pg \
  -e POSTGRES_USER=bushel -e POSTGRES_PASSWORD=bushel -e POSTGRES_DB=bushel_test \
  -p 5544:5432 postgres:16

# run the suite against it
export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test
uv run pytest
```

## Frontend development

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173
npm test
```

## Kroger setup (Phase 4)

Pushing a list to a real Kroger cart needs a registered Kroger developer app.

1. Create an app at https://developer.kroger.com with scopes `product.compact`,
   `cart.basic:write`, `profile.compact`, and redirect URI
   `http://localhost:8000/auth/callback`.
2. Put the credentials in `backend/.env`:
   ```
   KROGER_CLIENT_ID=...
   KROGER_CLIENT_SECRET=...
   KROGER_REDIRECT_URI=http://localhost:8000/auth/callback
   ```
3. Bring the stack up (`docker compose up`). If a standalone `bushel-pg` test container is
   running it will conflict with the Compose `db` on port 5432 — `docker stop bushel-pg` first.

### Manual smoke test (verifies the live integration)

1. Web app → **Kroger** tab → **Connect Kroger** → authorize on Kroger → you land back in the
   app. `GET /kroger/status` should report connected (a `kroger_auth` row exists).
2. Enter your zip → **Find stores** → **Use this store** to set the home store on the draft.
3. Build a draft list (Recipes → add to list) with at least one item.
4. **Match & send** tab → **Find product** for an item → products with price/stock appear →
   **Choose** one. Confirm the item shows the chosen product and a sane purchase quantity.
5. **Send to Kroger cart** (PICKUP) → per-item results show "added", the list is marked
   `sent_to_kroger`, and a `purchase_log` row is written.
6. Open the Kroger app/site and confirm the item is really in your cart. Checkout and
   pickup/delivery slot selection happen in Kroger's own app — that's the end of Bushel's job.

## Architecture

API-first: FastAPI backend + React frontend + Postgres, all via Docker Compose. The backend is
split into focused modules; fuzzy logic (parsing, matching, pantry guesses) is isolated from
deterministic logic (consolidation math, Kroger calls). A future iOS client reuses the same API.
