# Bushel

Bushel is a personal (single-user) web app that turns recipes into a consolidated grocery list
and pushes it straight into your Kroger cart. It merges duplicate ingredients across recipes,
sums and unit-converts their quantities, translates totals into purchasable packages, remembers
which Kroger product you buy for each ingredient, and uses a self-tracked purchase history to
ask "you bought this recently — do you still have it?" before adding things.

It's built API-first (FastAPI + Postgres) with a responsive React front end, and runs as a
Docker Compose stack so it can move from your laptop to a home server or the cloud as a config
change rather than a rewrite.

## What it does

- **Add recipes three ways:**
  - **URL import** — scrapes the page (`recipe-scrapers`), with a Claude fallback for sites that
    have no structured data.
  - **Manual entry** — type a title and ingredients; paste a messy block and let Claude
    **extract** just the ingredient lines.
  - **Photo** — snap or upload one or more photos of a recipe (cookbook page, handwritten card,
    screenshot) and Claude vision reads it into a recipe. Photos are read once and never stored.
- **Parse & canonicalize ingredients** — each raw line becomes `{qty, unit, name}` and resolves
  to a shared *canonical ingredient*, so "AP flour" and "all-purpose flour" are the same thing
  everywhere. Low-confidence parses are flagged for one-tap review on the recipe page.
- **Build a grocery list** — pick recipes and servings; Bushel consolidates them into one list,
  merging identical ingredients, summing quantities with unit conversion (`pint`), and
  translating each total into a **purchase quantity** (e.g. "3 cups flour → 1 bag").
- **Staples** — keep a list of always-buy items (milk, eggs…) and toggle them onto any trip.
- **Pantry "still have it?"** — items bought recently (per the purchase log) are flagged so you
  can drop them from the trip instead of re-buying.
- **Match to Kroger products** — confirm a product once and Bushel remembers it forever; a
  searchable picker shows price, package size, and stock level for your home store.
- **Send to cart** — pushes the confirmed items to your real Kroger cart (pickup or delivery) and
  records what was sent. You finish checkout and slot selection in Kroger's own app.

The UI is segmented and mobile-first (designed to be used from a phone): a **Recipes** list, a
**recipe detail** page that surfaces the rows needing review, and a grocery-list screen split
into **Items · Staples · Cart**.

## Architecture & design decisions

API-first: the React app talks to FastAPI over JSON, and the backend is split into focused
modules. The guiding principle is a hard boundary between **fuzzy** logic (parsing, matching,
pantry guesses) and **deterministic** logic (consolidation math, Kroger calls) — the parts that
can be wrong are isolated from the parts that must be exact.

```
React web app  ──JSON──▶  FastAPI  ──▶  Postgres (your data)
                                   └──▶  Kroger Public API (products / locations / cart)
                                   └──▶  Anthropic (Claude) for parsing & photo reading
```

Backend modules (`backend/app/`): `recipes/` (import + ingredient editing), `ingredients/`
(parse a line, canonicalize names), `consolidate/` (merge + sum + unit-convert + purchase math —
**deterministic, no LLM**), `staples/`, `pantry/` (purchase log + "still have it?"), `matching/`
(ingredient → Kroger product), `kroger/` (OAuth, product/location search, cart push), `settings/`
(home store), and `llm/` (the single Anthropic integration point).

Decisions worth knowing:

- **The `ingredients` table is the hub.** Recipes, the product map, list items, staples, and
  purchase history all point at canonical ingredients — so the remembered Kroger pick and the
  buy-history follow the *ingredient*, not the recipe.
- **One LLM integration point.** Everything Claude does goes through `llm/client.py` using
  structured outputs (Pydantic). The model is `claude-haiku-4-5` (multimodal — the same client
  reads recipe photos). The LLM is always a *fallback or assist*: library parsers run first, and
  anything the LLM touched (or any unparseable quantity) is marked `needs_review` so you can
  confirm it rather than trusting a guess.
- **Kroger's cart is write-only and there is no purchase-history API.** You can add to a cart but
  not read it back, and Kroger exposes no order history. So Bushel keeps its own append-only
  `purchase_log`, written when a list is sent — that log is the *only* source of the pantry
  "still have it?" prompts.
- **`total_qty` vs `purchase_qty`.** List items store both what the recipes need and how many
  packages to actually buy; the consolidation → purchasable translation is explicit, not implied.
- **Incompatible units aren't fake-merged.** "2 cloves garlic" + "1 tbsp garlic" can't be summed,
  so Bushel keeps separate sub-quantities (the `quantities` JSONB) and shows both rather than
  inventing a wrong total. Same philosophy throughout the error handling: never silently lose or
  fabricate data — flag it for review.
- **Confirm once, remember forever.** First time an ingredient is matched you pick the product;
  after that it resolves silently from `ingredient_product_map`.
- **Postgres even locally.** Keeping a real database (not SQLite) means moving to a home server or
  cloud is a connection-string change, not a migration.
- **Single-tenant, no auth.** There are no user accounts — the app assumes one user and the
  network is the trust boundary. Multi-user would mean adding auth and threading a user/household
  id through the schema; it's intentionally out of scope.
- **The draft list is recomputed on change.** Adding/removing recipes or staples rebuilds the
  consolidated draft so the list stays consistent.

The original design rationale and per-phase specs live in `docs/superpowers/specs/`; the
implementation plans in `docs/superpowers/plans/`.

## Tech stack

- **Backend:** FastAPI, SQLAlchemy, Pydantic, Alembic (migrations), `recipe-scrapers`,
  `ingredient-parser`, `pint` (unit conversion), Anthropic SDK. Managed with `uv`.
- **Frontend:** React + TypeScript + Vite + Tailwind CSS; Vitest + Testing Library.
- **Database:** Postgres 16.
- **Packaging:** Docker Compose (`db`, `api`, `web`).

## Data model (Postgres)

`recipes` / `recipe_ingredients` (raw + parsed lines) · `ingredients` (canonical hub, with
aliases/category/default purchase unit) · `ingredient_product_map` (remembered Kroger product per
ingredient) · `grocery_lists` / `grocery_list_recipes` / `grocery_list_items` (a trip, its
recipes, and the consolidated lines) · `staples` / `grocery_list_staples` · `purchase_log`
(append-only buy history) · `kroger_auth` (single OAuth token row) · `app_settings` (home store).

## Running it

### Quick start (Docker Compose)

```bash
cp .env.example .env      # then fill in the values below
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000 (health at `/health`)

`.env` values:

| Variable | What it is |
|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Postgres credentials for the `db` container |
| `DATABASE_URL` | e.g. `postgresql+psycopg://bushel:bushel@db:5432/bushel` (host is the compose service name `db`) |
| `KROGER_CLIENT_ID` / `KROGER_CLIENT_SECRET` / `KROGER_REDIRECT_URI` | Kroger developer app credentials (see below) |
| `ANTHROPIC_API_KEY` | Claude key, used for parsing, extraction, and photo reading |
| `VITE_API_URL` | Where the browser reaches the API (baked into the web build — see below) |
| `CORS_ORIGINS` | JSON array of browser origins allowed to call the API, e.g. `["http://localhost:5173"]` |
| `PANTRY_RECENT_DAYS` | "Bought recently" window for pantry prompts (default 14) |

### Using it from your phone / home network

The iPhone can't use `localhost` (that's the phone itself), so point it at the host's LAN IP:

1. Set `VITE_API_URL=http://<host-lan-ip>:8000` and add that web origin to `CORS_ORIGINS`,
   e.g. `["http://<host-lan-ip>:5173","http://localhost:5173"]`.
2. `docker compose up --build` — the `--build` matters: `VITE_API_URL` is compiled into the web
   bundle at build time, so a plain restart won't pick up a new address.
3. On the phone (same Wi-Fi): open `http://<host-lan-ip>:5173`.

For an always-on setup, run the same stack on a small home box (mini PC / Pi / NAS) with
`restart: unless-stopped`, give it a DHCP reservation so the address is stable, and back up the
Postgres volume. To reach it from outside the house without exposing it publicly, a private mesh
like Tailscale is the simplest safe option. (Note: because `VITE_API_URL` is build-time, a fixed
hostname or a future reverse-proxy `/api` setup avoids rebuilding when the address changes.)

### Deploy on a home box via Cloudflare (always-on, at bushel.havrilla.dev)

Run the stack on any always-on machine that has Docker, fronted by a Cloudflare Tunnel — no
port-forwarding, no static IP, automatic HTTPS, and login-gating via Cloudflare Access. The web
container reverse-proxies `/api` to the API, so the app is single-origin and nothing hard-codes
an address.

1. **Box:** install Docker + Docker Compose on the host (Pi, mini-PC, or old laptop — images are
   multi-arch).
2. **Cloudflare Tunnel:** with `havrilla.dev` on Cloudflare, go to **Zero Trust → Networks →
   Tunnels**, create a tunnel, and copy its token into `.env` as `TUNNEL_TOKEN`. Add a public
   hostname `bushel.havrilla.dev` → service `http://web:80`.
3. **Cloudflare Access (login-gating):** in **Zero Trust → Access → Applications**, add an app
   for `bushel.havrilla.dev` with two policies — a **Bypass** rule for your home public IP (so
   you're auto-logged-in on your Wi-Fi) and an **Allow** rule for your email (login required
   elsewhere).
4. **Kroger:** in the Kroger developer portal, add redirect URI
   `https://bushel.havrilla.dev/api/auth/callback`. Set `KROGER_REDIRECT_URI` to the same value
   in `.env`.
5. **Env:** in `.env`, set `VITE_API_URL=/api`, the `KROGER_REDIRECT_URI` above, and
   `TUNNEL_TOKEN`. Then on the box:

   ```bash
   docker compose up -d --build
   ```

Open `https://bushel.havrilla.dev`. The DHCP/IP problem is gone — the tunnel dials out and the
app is same-origin, so the host's address never matters.

### Backend development

```bash
cd backend
uv sync
export DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5432/bushel
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

### Frontend development

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173
```

### Running tests

Backend:

> ⚠️ **The test fixture (`tests/conftest.py`) runs `Base.metadata.drop_all()` on teardown
> against whatever `DATABASE_URL` points at.** Never run the suite against your dev database — it
> will wipe your data. Always point tests at a throwaway database on a different port.

```bash
# one-time: a disposable test Postgres on 5544 (separate from the dev DB on 5432)
docker run -d --name bushel-test-pg \
  -e POSTGRES_USER=bushel -e POSTGRES_PASSWORD=bushel -e POSTGRES_DB=bushel_test \
  -p 5544:5432 postgres:16

# run the suite against it
cd backend
DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest
```

Frontend:

```bash
cd frontend
npm test          # vitest
npx tsc -b        # type-check
npm run build     # production build
```

## Kroger setup

Pushing a list to a real Kroger cart needs a registered Kroger developer app.

1. Create an app at https://developer.kroger.com with scopes `product.compact`,
   `cart.basic:write`, `profile.compact`, and redirect URI
   `http://localhost:8000/auth/callback`.
2. Put the credentials in `.env` (`KROGER_CLIENT_ID`, `KROGER_CLIENT_SECRET`,
   `KROGER_REDIRECT_URI`).
3. Bring the stack up. If a standalone `bushel-test-pg` container is running it will conflict with
   the Compose `db` on port 5432 — stop it first, or it uses a different port (5544).

> Kroger's API is **write-only** for the cart and exposes no order history. Bushel only *adds* to
> your cart; checkout and pickup/delivery slot selection happen in Kroger's own app. Using the
> Kroger Connect flow from a phone requires the redirect URI to be reachable at the host's
> address (the bundled config assumes `localhost`).

### Manual smoke test (verifies the live integration)

1. **Kroger** tab → **Connect Kroger** → authorize → land back in the app; `/kroger/status` shows
   connected.
2. Enter your zip → **Find stores** → **Use this store** to set the home store.
3. Add a recipe (URL, manual, or photo) and add it to the list.
4. **Cart** tab → choose a product for each item (price/stock shown) → confirm.
5. **Send to cart** (pickup) → per-item results show "added", the list is marked
   `sent_to_kroger`, and `purchase_log` rows are written.
6. Open the Kroger app and confirm the items are really in your cart.

## Project layout

```
backend/app/
  recipes/      import (URL / manual / photo), ingredient add/edit/delete
  ingredients/  parse "2 cups flour", canonicalize names
  consolidate/  merge + sum + unit-convert + purchase math (deterministic)
  staples/      always-buy items, toggle onto a trip
  pantry/       purchase log + "still have it?" prompts
  matching/     ingredient → Kroger product, remembered map, cart send
  kroger/       OAuth tokens, product/location search, cart push
  settings/     home store
  llm/          single Anthropic client (parse, extract, photo vision)
frontend/src/
  recipes/      RecipeList, AddRecipe, RecipeDetail, GroceryList (Items/Staples/Cart), KrogerSetup
  components/ui/ shared primitives (Button, Card, SegmentedControl, …) + design tokens
docs/superpowers/  specs/ (design decisions) and plans/ (implementation plans)
```

## Status & non-goals

The MVP is complete: recipe import (URL/manual/photo), parsing & canonicalization,
consolidation, staples, pantry prompts, product matching, and Kroger cart push, with a
responsive web UI. Deliberately out of scope: multi-user accounts/sharing, non-Kroger stores,
order placement/checkout (Kroger's API can't), and nutrition/budgeting/meal-calendar features.
