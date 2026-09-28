# VerifyMeasure - Production Deployment

Backend: FastAPI + PostgreSQL. Frontend: static HTML/CSS/JS.

**Section A covers deploying on Render (the free-tier demo path).**
Sections 1-10 cover self-hosting with systemd and nginx, and apply to any
provider. All commands are run from the `backend/` directory unless stated
otherwise. Replace every `verifymeasure.example` placeholder with your real
domain.

---

# Part A - Render deployment (free tier)

## A1. What you get, and what it costs

| Piece | Service | Plan | Limitation |
| --- | --- | --- | --- |
| API | Render Web Service | Free | Spins down after 15 min idle; first request after that takes 30-60s |
| Frontend | Render Static Site | Free | No spin-down, CDN-backed |
| Database | Neon PostgreSQL | Free | 0.5 GB, 100 CU-hours/month, no expiry. Scales to zero after 5 min idle |

The API sleeping is the one real annoyance. For a demo, open the API URL once
right before you start presenting so it is warm.

## A2. The database: Neon

**Decision: Neon PostgreSQL.** Render's own free PostgreSQL **expires after 30
days**, which makes it a poor choice for a competition demo that may be judged
later. The free external options do not expire:

| Provider | Free tier | Expiry | Notes |
| --- | --- | --- | --- |
| **Neon** | 0.5 GB, 100 CU-hours/month | No expiry | **Chosen.** Standard PostgreSQL connection string, no card required. Scales to zero after 5 min idle. |
| Supabase | 500 MB, 2 projects | No expiry, but pauses after ~7 days idle | Adds 1-2s cold start after a pause. |
| Render PostgreSQL | 256 MB | **30 days** | Not recommended for a demo. |

To create the Neon project:

1. Sign up at <https://neon.tech> and create a project.
2. Choose the region closest to the Render region you will pick.
3. Open **Connection Details**, select the pooled or direct connection string.
4. Copy it. It looks like `postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require`.

Important for Neon specifically: prefer the **direct** (non-pooled) connection
string. This app uses standard SQLAlchemy and does not need a pooler, and the
pooler sits in front of a proxy that some SQLAlchemy versions negotiate poorly.
Keep the `?sslmode=require` query parameter exactly as Neon gives it to you;
`backend/app/core/database.py` passes the whole string to `create_engine()`
unchanged.

One Neon-specific caveat worth knowing before the demo: scale-to-zero means the
first query after five idle minutes takes a couple of seconds while the compute
resumes. Cold starts the database and the API service are independent, so the
worst case is the sum of the two.

Your existing local `sih_2026` database is untouched by any of this. To load
your local data into the new database later, use `pg_dump` / `pg_restore` or
the Neon's import flow. Do that as a separate step, after the schema is live.

## A3. Push the repository

```bash
cd "C:\Users\lenovo\OneDrive\Desktop\SIH 2026"
git init
git add -A
git status                 # confirm .env, venv/ and caches are absent
git commit -m "VerifyMeasure SIH verification system"
git remote add origin https://github.com/<YOUR_USER>/<YOUR_REPO>.git
git push -u origin main
```

## A4. Create the services from the blueprint

`render.yaml` at the repository root declares both services. In the Render
dashboard: **New -> Blueprint**, then point it at the repository. Render will
offer to import the values for the variables marked `sync: false`; fill those in
when prompted.

Or create them by hand, which is often easier to follow:

**Backend**

| Field | Value |
| --- | --- |
| Runtime | Python |
| Root Directory | `backend` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | see below |
| Health Check Path | `/health` |
| Instance Type | Free |

Start command:

```
uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1 --proxy-headers --forwarded-allow-ips '*' --no-reload
```

`--workers 1` is deliberate. `app/main.py` runs `Base.metadata.create_all()` and
`upgrade_workflow_schema()` at import time, so two workers starting at once can
race each other issuing identical DDL against a fresh database. A free instance
is 0.5 GB / 0.1 CPU and gains nothing from a second worker anyway.

**Frontend**

| Field | Value |
| --- | --- |
| Type | Static Site |
| Build Command | leave empty |
| Publish Path | `./frontend` |

The frontend lives in a plain `frontend/` directory at the repository root. It
used to be nested twice under a folder name containing a trailing apostrophe,
which made the publish path awkward to type; the rename is the only change, and
no page links across folders, so nothing else needed updating.

## A5. Environment variables on the backend service

Set these in the Render dashboard under **Environment**. Never put a real value
in `render.yaml` or any file in the repository.

| Key | Value | Notes |
| --- | --- | --- |
| `ENVIRONMENT` | `production` | Enables the strict validation described below |
| `PYTHON_VERSION` | `3.12.11` | Pinned; also set in `backend/.python-version` |
| `DEBUG` | `false` | Startup aborts if true |
| `RELOAD` | `false` | Startup aborts if true |
| `DATABASE_URL` | your connection string | From A2. Never localhost. |
| `JWT_SECRET_KEY` | Render "Generate" button, or see below | Minimum 32 characters |
| `CORS_ALLOWED_ORIGINS` | the frontend URL, e.g. `https://verifymeasure-web.onrender.com` | Must be exact, no trailing slash, no `*` |
| `FRONTEND_URL` | same value as above | Drives QR and verification URLs |
| `PUBLIC_VERIFICATION_URL` | same value as above | Defaults to `FRONTEND_URL` if omitted |
| `BACKEND_URL` | the API's own URL | Optional |
| `ADMIN_BOOTSTRAP_TOKEN` | Render "Generate" button | One-time admin bootstrap |

To generate a JWT secret yourself:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## A6. Point the frontend at the API

One line, in `frontend/js/config.js`:

```js
var API_BASE_URL_DEFAULT = "https://verifymeasure-api.onrender.com";
```

Replace the placeholder with the API URL Render gave you, then commit and push.
Render redeploys the static site automatically.

Order matters: the frontend's URL is needed for the API's `CORS_ALLOWED_ORIGINS`,
and the API's URL is needed for the frontend config. Create both services first,
then set the env var on the API, then edit `config.js` and push.

## A7. The startup guard

With `ENVIRONMENT=production`, the app refuses to boot and prints every problem
it found if any of these is true:

- `DATABASE_URL` missing, not a `postgresql://` URL, or pointing at localhost
- `JWT_SECRET_KEY` missing or shorter than 32 characters
- `FRONTEND_URL` missing or not `https://`
- `CORS_ALLOWED_ORIGINS` missing, empty, or containing `*`
- `DEBUG` or `RELOAD` true

This turns a silent misconfiguration into an obvious deploy failure, which
matters on a platform where you are reading build logs in a hurry.

---

# Part B - Self-hosted deployment (systemd + nginx)

## 1. Prerequisites

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
```

You also need a reachable PostgreSQL instance and a TLS-terminating reverse
proxy (nginx, Caddy, or a cloud load balancer) in front of the API.

---

## 2. Production environment variables

The backend reads configuration **only** from the process environment when
`ENVIRONMENT=production`. `backend/.env` is ignored in that mode, so a stale
local file can never supply production credentials.

Create the file:

```bash
cp .env.production.example .env.production
```

Then edit `.env.production` and set at minimum:

| Variable | Required | Notes |
| --- | --- | --- |
| `ENVIRONMENT` | yes | Must be `production` |
| `DATABASE_URL` | yes | `postgresql://user:pass@host:5432/dbname`; must not contain `@localhost` |
| `JWT_SECRET_KEY` | yes | At least 32 characters. Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `FRONTEND_URL` | yes | `https://` frontend origin. Drives QR and public verification URLs |
| `CORS_ALLOWED_ORIGINS` | yes | Comma-separated exact origins. `*` is rejected |
| `BACKEND_URL` | no | Public API base URL, defaults to unset |
| `PUBLIC_VERIFICATION_URL` | no | Defaults to `FRONTEND_URL` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | Default `60` |
| `ADMIN_BOOTSTRAP_TOKEN` | no | One-time bootstrap secret |
| `DEBUG` | no | Must be `false` |
| `RELOAD` | no | Must be `false` |

Startup **aborts** with a `RuntimeError` listing every problem if any required
variable is missing, if `JWT_SECRET_KEY` is too short, if `DATABASE_URL` points
at localhost, if `FRONTEND_URL` is not `https://`, if `CORS_ALLOWED_ORIGINS`
contains `*`, or if `DEBUG`/`RELOAD` are on.

Load the file into the current shell (Linux/macOS):

```bash
set -a && . ./.env.production && set +a
```

On Windows PowerShell:

```powershell
Get-Content .env.production | Where-Object { $_ -match '^\s*[^#].*=' } | ForEach-Object {
    $k, $v = $_ -split '=', 2
    [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), 'Process')
}
```

Verify the configuration parses before starting the server:

```bash
python -c "from app.core.config import settings; print(settings.ENVIRONMENT, settings.CORS_ALLOWED_ORIGINS)"
```

---

## 3. Database

`DATABASE_URL` is the single source of truth. `backend/app/core/database.py`
builds the SQLAlchemy engine from it directly, so pointing it at the production
PostgreSQL instance is the only step needed. There is no separate host/port
configuration to keep in sync.

Verify connectivity (read-only, safe against the existing database):

```bash
python -c "from sqlalchemy import create_engine, text; from app.core.config import settings; e=create_engine(settings.DATABASE_URL); print(e.connect().execute(text('select current_database(), version()')).first())"
```

Schema setup is idempotent and runs at application start
(`Base.metadata.create_all` plus `upgrade_workflow_schema()`), which only adds
missing tables and `ADD COLUMN IF NOT EXISTS` columns. It does not drop or
truncate anything.

---

## 4. Production startup command

Reload and the auto-reloader are explicitly disabled.

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers --forwarded-allow-ips '*' --no-reload
```

`backend/Procfile` encodes the same command with `${PORT}` and
`${WEB_CONCURRENCY}` defaults for PaaS hosts.

Serve it as a managed service rather than a foreground process. systemd unit:

```ini
[Unit]
Description=VerifyMeasure API
After=network.target

[Service]
Type=simple
User=verifymeasure
WorkingDirectory=/opt/verifymeasure/backend
EnvironmentFile=/opt/verifymeasure/backend/.env.production
ExecStart=/opt/verifymeasure/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers --forwarded-allow-ips '*' --no-reload
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now verifymeasure-api
sudo systemctl status verifymeasure-api
```

---

## 5. CORS

`allow_origins` in `backend/app/main.py` is taken from `CORS_ALLOWED_ORIGINS`.
In production the list must be non-empty and must not contain `*`; the process
refuses to start otherwise. `allow_credentials=True` is kept, which is correct
because the API authenticates with Bearer tokens, and browsers reject the
combination of credentials plus a wildcard origin anyway.

Set it to the exact frontend origins, comma-separated:

```
CORS_ALLOWED_ORIGINS=https://verifymeasure.example
```

---

## 6. Frontend configuration

The API base URL lives in one place: `frontend/js/config.js`.
No page hardcodes a host any more. Resolution order:

1. `<meta name="api-base-url" content="...">` in the page `<head>`
2. `window.APP_CONFIG.API_BASE_URL` set by an injected script
3. `API_BASE_URL_DEFAULT` inside `js/config.js`

`js/config.js` also exposes `window.APP_CONFIG.FRONTEND_URL`, derived from
`window.location.origin` unless a `frontend-base-url` meta tag is present, so
the public verification page always uses the deployed frontend domain.

To point the deployed site at the production API, either set the meta tag in
each page or edit the default in `config.js`:

```js
var API_BASE_URL_DEFAULT = "https://api.verifymeasure.example";
```

`https://api.verifymeasure.example` is a placeholder. Replace it with the real
API origin, and make sure that origin is reachable from the browser and is not
blocked by the page's CSP.

---

## 7. Certificate PDFs, QR codes, public verification

- `backend/app/services/qr_service.py::build_verification_url` builds
  `{PUBLIC_VERIFICATION_URL or FRONTEND_URL}/verify.html?token=<qr_token>`.
- `backend/app/services/pdf_service.py` embeds that same URL in the printed QR
  code. It previously fell back to a hardcoded `legalmetrology.gov.in`; that
  fallback now goes through the configured production domain.
- Certificates already issued before this change keep the `qr_code_url` value
  stored in the `certificates` table, since the PDF prefers the stored column.
  Re-issue or backfill that column if those certificates point at an old
  domain.

Confirm the domain that will be printed:

```bash
python -c "from app.services.qr_service import build_verification_url; print(build_verification_url('TESTTOKEN'))"
```

---

## 8. Static frontend hosting

Serve the `frontend/` directory over HTTPS from any static host or CDN. The API
is on a different origin, so CORS above is what allows it.

Minimal nginx server block for the frontend:

```nginx
server {
    listen 443 ssl http2;
    server_name verifymeasure.example;

    ssl_certificate     /etc/letsencrypt/live/verifymeasure.example/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/verifymeasure.example/privkey.pem;

    root /var/www/verifymeasure;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

nginx proxy in front of the API:

```nginx
server {
    listen 443 ssl http2;
    server_name api.verifymeasure.example;

    ssl_certificate     /etc/letsencrypt/live/api.verifymeasure.example/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.verifymeasure.example/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 9. Tests

```bash
cd backend
python test_phase1.py
python test_phase2.py
python test_phase3.py
python test_http_endpoints.py
```

Each script starts a short-lived uvicorn instance on its own port against the
configured `DATABASE_URL`. They bind to `127.0.0.1` by design; that is test
harness plumbing, not production configuration, and should not be changed.

---

## 10. Post-deploy verification

```bash
curl -fsS https://api.verifymeasure.example/health
# {"status":"healthy","environment":"production"}
```

Then confirm in a browser, with devtools open:

1. Load `https://verifymeasure.example/verify.html?token=<token>` and confirm
   the request to the API is not blocked by CORS.
2. Issue a test certificate, open its PDF, and scan the QR code. It must open
   the production verification page.
3. Check that no request goes to `127.0.0.1` or `localhost`.

---

## 11. End-to-end workflow test

Run this once against the deployed system. It exercises every stage and is the
check to do before a demo.

| Step | How | Expected |
| --- | --- | --- |
| 1. Bootstrap admin | `POST /auth/bootstrap-admin` with the `ADMIN_BOOTSTRAP_TOKEN` | 201, admin created |
| 2. Login | `POST /auth/login` | 200, returns `access_token` |
| 3. Register instrument | `POST /instruments/` | 201 |
| 4. Create application | `POST /applications/` | 201, `APP-...` number |
| 5. Create inspection | `POST /inspections/` with result `Pass` | 201 |
| 6. Decide | `POST /applications/{id}/decision` with `approved` | 200 |
| 7. Issue certificate | `POST /certificates/issue` | 200, certificate number + QR token |
| 8. PDF | `GET /certificates/number/{cert}/pdf` | 200, `application/pdf` |
| 9. QR image | `GET /certificates/token/{token}/qr` | 200, PNG |
| 10. Public verify | `GET /certificates/verify/{token}` | 200, `is_authentic: true` |
| 11. QR scan | open the PDF's QR code with a phone | lands on `verify.html?token=...` on the production domain |

Step 11 is the one that catches a misconfigured `FRONTEND_URL`, because the QR
image itself still renders fine even when the URL inside it points at the wrong
domain. Read the URL with a QR scanner app rather than trusting that the image
loaded.

To bootstrap the admin, send the token in the request body:

```bash
curl -X POST https://api.verifymeasure.example/auth/bootstrap-admin \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"<STRONG_PASSWORD>","full_name":"Administrator","bootstrap_token":"<ADMIN_BOOTSTRAP_TOKEN>"}'
```

The endpoint is one-shot: once any administrator exists it returns 409, and
`ADMIN_BOOTSTRAP_TOKEN` should be cleared from the Render environment
afterwards.

---

## Outstanding items not changed here

- `Base.metadata.create_all()` and `upgrade_workflow_schema()` still run at
  import time. They are idempotent and non-destructive, but a migration tool
  such as Alembic would be the right long-term replacement. This is also why
  the worker count is pinned to 1.
- The frontend folder is nested twice and its name ends in a stray apostrophe.
  Harmless, but awkward in build settings.
- The root-level `app/` directory is older scratch code superseded by
  `backend/app/`. It is committed for reference only; nothing imports it, and
  the deployed service uses `backend/app` exclusively.
- Secrets present in the local `backend/.env` were development credentials.
  They are gitignored, and if the file was ever committed before this `.gitignore`
  existed they should be rotated.
