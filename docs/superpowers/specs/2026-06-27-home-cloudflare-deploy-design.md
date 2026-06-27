# Home-box + Cloudflare deploy — design

Date: 2026-06-27

## Goal

Host Bushel for a single user (yourself) on an always-on home box, reachable at
`https://bushel.havsfamily.com` with HTTPS and login-gating, without port-forwarding, a static IP,
or the build-time IP coupling that currently breaks the app when DHCP reassigns the host. Keep it
single-tenant (no in-app accounts); Cloudflare Access controls *who* can open it.

## Background / current state

- The app runs as a Docker Compose stack: `db` (Postgres 16), `api` (FastAPI, port 8000),
  `web` (nginx serving the built React SPA, container port 80 → host 5173).
- `frontend/Dockerfile` bakes `VITE_API_URL` at **build time** (build arg, default
  `http://localhost:8000`); `frontend/nginx.conf` only serves the SPA (`try_files … /index.html`),
  it does not proxy the API. So the browser calls the API cross-origin at whatever absolute URL
  was baked in — which is why a DHCP IP change breaks the running app.
- `frontend/src/api.ts`: `BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000"`;
  every call is `fetch(\`${BASE_URL}/...\`)`. Photo upload posts multipart to
  `${BASE_URL}/recipes/import-photo`.
- `backend/app/kroger/router.py` `callback()` (path `/auth/callback`, no router prefix) redirects
  the browser after OAuth to `get_settings().cors_origins[0]` — an absolute origin (currently a
  LAN IP). The Kroger login URL is built with `KROGER_REDIRECT_URI`.
- CORS is configured from `cors_origins` (env `CORS_ORIGINS`), already forwarded to the `api`
  service in compose.

## Architecture

A Cloudflare Tunnel fronts the stack; the `web` nginx becomes a single-origin reverse proxy so
the SPA and the API share one origin and no absolute host is ever baked in.

```
Cloudflare edge ──(outbound tunnel)──▶ cloudflared ──▶ web:80 (nginx)
  bushel.havsfamily.com (HTTPS)                           ├── serves the SPA
  Cloudflare Access in front                            └── /api/* ─▶ api:8000  ─▶ db
```

### 1. Single-origin reverse proxy (`frontend/nginx.conf`)

Add an `/api/` location that proxies to the api service, stripping the `/api` prefix via the
trailing slash on `proxy_pass`, and raise the body limit so photo uploads (multi-MB) aren't
rejected by nginx's 1 MB default:

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

`proxy_pass http://api:8000/` (trailing slash) maps `/api/recipes` → `/recipes` on the api, so
the backend routes are unchanged. `api` resolves over the compose network.

### 2. Frontend talks to a relative `/api` (build arg only)

The compose `web` build sets `VITE_API_URL=/api`, so `BASE_URL` becomes `/api` and every call is
same-origin (`/api/recipes`, `/api/recipes/import-photo`, …). No code change in `api.ts` — its
`?? "http://localhost:8000"` default still serves `npm run dev` (where no proxy exists and the
dev server talks to `localhost:8000` directly). Only the container build uses `/api`.

### 3. Kroger OAuth callback becomes host-independent (`backend/app/kroger/router.py`)

Change the post-OAuth redirect from `cors_origins[0]` (absolute IP) to a relative path so it works
behind any host:

```python
    # Send the user back to the web app (relative → works behind the tunnel / any host).
    return RedirectResponse(url="/kroger", status_code=307)
```

Behind the proxy the browser is at `…/api/auth/callback`; a redirect to `/kroger` lands on the
SPA's Kroger page (showing "connected"). `KROGER_REDIRECT_URI` becomes
`https://bushel.havsfamily.com/api/auth/callback` (proxied to the api's `/auth/callback`), and that
URI is registered in the Kroger developer portal. Update the existing callback test to assert the
relative `/kroger` redirect.

### 4. Compose: tunnel + restart policies (`docker-compose.yml`)

- Add a `cloudflared` service:
  ```yaml
  cloudflared:
    image: cloudflare/cloudflared:latest
    command: tunnel --no-autoupdate run
    environment:
      TUNNEL_TOKEN: ${TUNNEL_TOKEN}
    restart: unless-stopped
    depends_on:
      - web
  ```
  Token-based ("remotely-managed") tunnel: the hostname → service route
  (`bushel.havsfamily.com` → `http://web:80`) is configured in the Cloudflare dashboard, so
  cloudflared only needs `TUNNEL_TOKEN`. It reaches `web` over the compose network; no published
  ports needed for the tunnel path.
- Add `restart: unless-stopped` to `db`, `api`, and `web`.
- Set the `web` build arg `VITE_API_URL: ${VITE_API_URL}` (already wired) and put `VITE_API_URL=/api`
  in the deploy `.env`.
- Drop the published host port on `api` (it's reachable only via the proxy now). Keep `web` on
  `5173:80` as a LAN fallback. `db` stays internal (or keep 5432 for local admin).

### 5. Cloudflare Access (dashboard, no code)

One Access application for `bushel.havsfamily.com` with two policies:
- **Bypass** — include: your home public IP (so you're auto-logged-in on your WiFi).
- **Allow** — include: your Google email (login required everywhere else).

The Kroger OAuth round-trip works under Access: Kroger redirects your *browser* back to
`…/api/auth/callback`, and the browser carries the Access session cookie, so no path bypass is
needed.

### 6. Docs (`.env.example`, `README.md`)

Document `TUNNEL_TOKEN`, `VITE_API_URL=/api`, and `KROGER_REDIRECT_URI=https://bushel.havsfamily.com/api/auth/callback`,
and add a short "Deploy on a home box via Cloudflare" section with the runbook below.

## Runbook (operator steps, not code)

1. Provision the box (anything that runs Docker — Pi/mini-PC/old laptop); install Docker + Compose.
2. Ensure `havsfamily.com` is on Cloudflare (nameservers). In **Zero Trust → Networks → Tunnels**:
   create a tunnel, copy its token → `TUNNEL_TOKEN`; add public hostname `bushel.havsfamily.com` →
   service `http://web:80`.
3. In **Zero Trust → Access → Applications**: add `bushel.havsfamily.com`; add the Bypass (home IP)
   and Allow (your email) policies.
4. In the **Kroger developer portal**: add redirect URI
   `https://bushel.havsfamily.com/api/auth/callback`.
5. Copy `.env` to the box (secrets + `TUNNEL_TOKEN`, `VITE_API_URL=/api`, the new
   `KROGER_REDIRECT_URI`); run `docker compose up -d --build`.

## Testing

- **Backend:** update `tests/test_kroger_router.py::test_callback_exchanges_code_and_saves`
  (which currently posts to `/auth/callback` with `follow_redirects=False` and asserts
  `status_code in (200, 307)`) to assert `status_code == 307` and
  `resp.headers["location"] == "/kroger"`. All other backend tests unchanged.
- **Reverse proxy:** verified manually after build — `curl -sS http://localhost:5173/api/health`
  returns `{"status":"ok"}` (proxied to the api), and `http://localhost:5173/` serves the SPA.
  (nginx config isn't unit-tested; the curl check goes in the runbook.)
- **Frontend:** existing Vitest suite unchanged (it mocks `fetch`; the relative base URL doesn't
  affect tests).

## Scope / non-goals

- **No multi-user / no in-app auth.** Cloudflare Access gates *who* can reach the single-tenant
  app; the schema and app are unchanged.
- No managed/cloud database, no secrets manager — `.env` on the box (Access + the tunnel are the
  boundary).
- Photos still not stored; no app-behavior changes beyond the callback redirect and the
  same-origin API base.
- Hardware choice is out of scope (any Docker host works; images are multi-arch).
