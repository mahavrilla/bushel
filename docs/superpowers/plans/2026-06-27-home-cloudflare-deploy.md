# Home-box + Cloudflare Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Bushel deployable on a home box behind a Cloudflare Tunnel at `https://bushel.havrilla.dev` — single-origin (no baked-in IP), the Kroger OAuth callback host-independent, photos uploadable through nginx, and the stack self-restarting.

**Architecture:** The `web` nginx becomes a reverse proxy (`/api/*` → `api:8000`) so the SPA and API share one origin and the frontend uses a relative `VITE_API_URL=/api`. A `cloudflared` service fronts the stack via an outbound tunnel. The Kroger callback redirects to a relative path. Cloudflare Access (dashboard, not code) gates the hostname.

**Tech Stack:** Docker Compose, nginx, Cloudflare Tunnel (`cloudflared`); FastAPI backend (pytest), React/Vite frontend (vitest).

**Spec:** `docs/superpowers/specs/2026-06-27-home-cloudflare-deploy-design.md`

**Backend tests run against the isolated test DB only:**
`cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest`

---

## File Structure

- `backend/app/kroger/router.py` (modify) — callback redirects to relative `/kroger`; drop the now-unused `get_settings` import.
- `backend/tests/test_kroger_router.py` (modify) — assert the callback's relative redirect.
- `frontend/nginx.conf` (modify) — add the `/api/` reverse-proxy location + `client_max_body_size`.
- `docker-compose.yml` (modify) — add the `cloudflared` service, `restart: unless-stopped` on `db`/`api`/`web`, drop the published `api` port.
- `.env.example` (modify) — document `TUNNEL_TOKEN`, `VITE_API_URL=/api`, the new `KROGER_REDIRECT_URI`.
- `README.md` (modify) — add a "Deploy on a home box via Cloudflare" section (the runbook).

---

### Task 1: Kroger callback redirects to a relative path

**Files:**
- Modify: `backend/app/kroger/router.py`
- Test: `backend/tests/test_kroger_router.py`

The callback currently redirects to `get_settings().cors_origins[0]` (an absolute IP). Behind the tunnel it must be host-independent, so redirect to the relative `/kroger` (the SPA's Kroger page). `get_settings` is used nowhere else in the file, so its import is removed.

- [ ] **Step 1: Update the failing test**

In `backend/tests/test_kroger_router.py`, replace the assertion in `test_callback_exchanges_code_and_saves` (currently `assert resp.status_code in (200, 307)`) so it pins the relative redirect. The test already uses `follow_redirects=False`. The full updated test body:

```python
def test_callback_exchanges_code_and_saves(db_session):
    kroger = MagicMock()
    kroger.authorize_url.return_value = "https://x/?state=STATE123"
    kroger.exchange_code.return_value = TokenResp(access_token="a", refresh_token="r", expires_in=1800)
    client = _client(db_session, kroger)
    from app.kroger import router as kr
    kr._PENDING_STATES.add("STATE123")
    resp = client.get("/auth/callback", params={"code": "c", "state": "STATE123"},
                      follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "/kroger"
    assert db_session.query(KrogerAuth).count() == 1
    kroger.exchange_code.assert_called_once_with("c")
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_kroger_router.py::test_callback_exchanges_code_and_saves -v`
Expected: FAIL — the redirect `location` is currently the `cors_origins[0]` origin, not `/kroger`.

- [ ] **Step 3: Implement**

In `backend/app/kroger/router.py`, change the end of `callback()`. Replace:

```python
    auth.save_tokens(db, token)
    db.commit()
    # Send the user back to the web app (functional; Phase 6 polishes this).
    origins = get_settings().cors_origins
    return RedirectResponse(url=origins[0] if origins else "/", status_code=307)
```

with:

```python
    auth.save_tokens(db, token)
    db.commit()
    # Send the user back to the web app. Relative so it works behind the tunnel / any host.
    return RedirectResponse(url="/kroger", status_code=307)
```

Then remove the now-unused import line `from app.config import get_settings` (line 11).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest tests/test_kroger_router.py -v`
Expected: PASS — the updated callback test plus all other Kroger router tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/kroger/router.py backend/tests/test_kroger_router.py
git commit -m "feat(kroger): redirect OAuth callback to a relative path"
```

---

### Task 2: nginx reverse-proxies the API (single origin)

**Files:**
- Modify: `frontend/nginx.conf`

The `web` nginx must serve the SPA *and* proxy `/api/*` → `api:8000` (stripping the `/api` prefix), with a raised body limit so multi-MB photo uploads aren't rejected by nginx's 1 MB default. This is config, verified by an integration curl after building the stack (no unit test).

- [ ] **Step 1: Implement the nginx config**

Replace the entire contents of `frontend/nginx.conf` with:

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;
    client_max_body_size 25m;

    location /api/ {
        proxy_pass http://api:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

(The trailing slash on `proxy_pass http://api:8000/` strips the `/api` prefix, so `/api/recipes` reaches the backend as `/recipes`. Docker DNS resolves `api`; compose `depends_on` orders startup.)

- [ ] **Step 2: Verify the proxy end-to-end**

This needs the stack built with the relative base URL. From the repo root, with a working `.env` (Postgres creds, `ANTHROPIC_API_KEY`, etc.):

Run:
```bash
VITE_API_URL=/api docker compose up -d --build db api web
sleep 5
curl -sS -m 5 http://localhost:5173/api/health      # expect: {"status":"ok"}
curl -sS -m 5 -o /dev/null -w "%{http_code}\n" http://localhost:5173/   # expect: 200 (SPA)
```
Expected: the first curl returns `{"status":"ok"}` (proxied to the api), the second returns `200`.

If you want to leave the stack down afterward: `docker compose down`.

- [ ] **Step 3: Commit**

```bash
git add frontend/nginx.conf
git commit -m "feat(web): reverse-proxy /api to the api service (single origin)"
```

---

### Task 3: Compose — cloudflared tunnel, restart policies, drop the api port

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Implement the compose changes**

Replace the entire contents of `docker-compose.yml` with:

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
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 3s
      retries: 10

  api:
    build: ./backend
    environment:
      DATABASE_URL: ${DATABASE_URL}
      CORS_ORIGINS: ${CORS_ORIGINS}
      KROGER_CLIENT_ID: ${KROGER_CLIENT_ID}
      KROGER_CLIENT_SECRET: ${KROGER_CLIENT_SECRET}
      KROGER_REDIRECT_URI: ${KROGER_REDIRECT_URI}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy

  web:
    build:
      context: ./frontend
      args:
        VITE_API_URL: ${VITE_API_URL}
    ports:
      - "5173:80"
    restart: unless-stopped
    depends_on:
      - api

  cloudflared:
    image: cloudflare/cloudflared:latest
    command: tunnel --no-autoupdate run
    environment:
      TUNNEL_TOKEN: ${TUNNEL_TOKEN}
    restart: unless-stopped
    depends_on:
      - web

volumes:
  bushel_pgdata:
```

(Changes vs. current: `restart: unless-stopped` on `db`/`api`/`web`; the `api` `ports:` block removed — it's reached only via the web proxy now; new `cloudflared` service. `web` keeps `5173:80` as a LAN fallback; `db` keeps `5432` for local admin.)

- [ ] **Step 2: Verify compose config parses**

Run: `docker compose config >/dev/null && echo OK`
Expected: `OK` (no YAML/interpolation errors). A missing `TUNNEL_TOKEN` in `.env` only produces an empty-value warning, not an error — that's fine until deploy time.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(deploy): add cloudflared tunnel + restart policies; drop api public port"
```

---

### Task 4: Document the deploy (.env.example + README)

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Update `.env.example`**

Replace the entire contents of `.env.example` with:

```bash
# Postgres
POSTGRES_USER=bushel
POSTGRES_PASSWORD=bushel
POSTGRES_DB=bushel

# Backend (note: host is the compose service name "db")
DATABASE_URL=postgresql+psycopg://bushel:bushel@db:5432/bushel

# Browser origins allowed to call the API. Irrelevant behind the single-origin
# reverse proxy (same-origin), but harmless to set for local/LAN use.
CORS_ORIGINS=["http://localhost:5173"]

# Kroger Public API (from developer.kroger.com)
KROGER_CLIENT_ID=
KROGER_CLIENT_SECRET=
# Local: http://localhost:8000/auth/callback
# Tunnel deploy: https://bushel.havrilla.dev/api/auth/callback
KROGER_REDIRECT_URI=http://localhost:8000/auth/callback

# Anthropic (Claude) — recipe/ingredient parsing and photo reading
ANTHROPIC_API_KEY=

# Frontend API base URL (baked into the web build).
# Tunnel deploy: /api  (same-origin via the nginx reverse proxy)
# Plain local/LAN:  http://<host>:8000
VITE_API_URL=/api

# Cloudflare Tunnel token (deploy only; from the Zero Trust dashboard)
TUNNEL_TOKEN=
```

- [ ] **Step 2: Add the deploy section to the README**

In `README.md`, immediately after the "Using it from your phone / home network" subsection (it ends with the paragraph about an always-on setup / Tailscale), insert this new subsection:

```markdown
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
```

- [ ] **Step 3: Commit**

```bash
git add .env.example README.md
git commit -m "docs: document the Cloudflare home-box deploy"
```

---

### Task 5: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Backend suite**

Run: `cd backend && DATABASE_URL=postgresql+psycopg://bushel:bushel@localhost:5544/bushel_test uv run pytest -q`
Expected: PASS — all backend tests, including the updated callback test.

- [ ] **Step 2: Frontend suite + build**

Run: `cd frontend && npm test && npx tsc -b && npm run build`
Expected: tests pass, no type errors, build succeeds. (The relative API base doesn't affect the Vitest suite — it mocks `fetch`.)

- [ ] **Step 3: End-to-end proxy smoke (local)**

Run (repo root, with a working `.env`):
```bash
VITE_API_URL=/api docker compose up -d --build db api web
sleep 5
curl -sS -m 5 http://localhost:5173/api/health
curl -sS -m 5 -o /dev/null -w "SPA %{http_code}\n" http://localhost:5173/
docker compose down
```
Expected: `{"status":"ok"}` from the proxied API and `SPA 200` from the web root.

- [ ] **Step 4: No commit unless incidental changes**

```bash
git status --short
```

---

## Notes for the implementer

- Backend tests MUST use the isolated test DB (`...@localhost:5544/bushel_test`).
- Tasks 2, 3, and 5's docker steps require Docker running locally; if a sandbox blocks Docker,
  report it — the config is still correct and can be verified on the deploy box.
- `cloudflared`, the Cloudflare dashboard setup, and the Kroger portal change are operator steps
  (documented in the README), not automated here. `TUNNEL_TOKEN` is supplied at deploy time.
- Don't change `frontend/src/api.ts` — its `?? "http://localhost:8000"` default still serves
  `npm run dev`; only the container build uses `VITE_API_URL=/api`.
