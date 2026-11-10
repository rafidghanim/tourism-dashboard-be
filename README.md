# Tourism Decision Support System Backend

FastAPI public API vertical slice for the Tourism Decision Support System platform.

## Scope

The backend provides the anonymous public read API and a runnable administrative workflow for the Tourism Overview frontend:

- `GET /health/live`
- `GET /health/ready`
- `GET /api/v1/public/overview`
- `GET /api/v1/public/visitor-distribution`
- `GET /api/v1/public/trends`
- `GET /api/v1/public/destinations`
- `GET /api/v1/public/destinations/{destination_id}`
- `GET /api/v1/public/destinations/ranking`
- `GET /api/v1/public/map-layers/visits`
- `GET /api/v1/public/metadata`

Administrative endpoints (development adapter):

- `GET /api/v1/internal/me`
- `GET|POST|PATCH /api/v1/internal/destinations`
- `POST /api/v1/internal/visitor-statistics`
- `POST /api/v1/internal/imports`
- `POST /api/v1/internal/imports/{id}/validate`
- `POST /api/v1/internal/imports/{id}/accept`
- `POST /api/v1/internal/publications`
- `GET /api/v1/internal/audit-logs`

The implementation currently uses `DemoPublicRepository`, an in-memory deterministic repository. Every fixture response is labeled:

> Data demonstrasi — bukan statistik resmi

Responses include `data_class=demonstration`, `is_demo=true`, dataset version `demo-2026-11-08-v1`, freshness, and warnings. The repository protocol in `app/public/repository.py` is the replacement seam for a future PostgreSQL/PostGIS implementation.

The admin workflow uses a durable SQLite adapter by default (`backend/data/tourism-admin.sqlite3`), with a repository seam for the planned PostgreSQL/PostGIS adapter. In local development only, `X-Demo-User: admin|editor|viewer` exercises the session/RBAC boundary. This adapter is intentionally not production authentication; configure the provider-agnostic OIDC session adapter before deployment.

## Local setup

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e 'backend[test,dev]'
```

Run the API:

```bash
uvicorn app.main:app --app-dir backend --reload
```

OpenAPI is available at `http://127.0.0.1:8000/docs` and `http://127.0.0.1:8000/openapi.json`.

Example request:

```bash
curl -i 'http://127.0.0.1:8000/api/v1/public/overview?region_id=surakarta&visitor_category=all'
```

All responses include `X-Request-ID`. Stable GET responses include an `ETag` and support `If-None-Match`.

To connect the Next.js dashboard to the public API, start the backend and set `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000` when running the frontend. Without that variable the frontend deliberately uses its visibly labeled local demonstration fixture. The `/admin` frontend page uses the same local demo identity header and is for development workflow validation only.

## Verification

From the repository root:

```bash
PYTHONPATH=backend python -m pytest backend/tests -q
ruff check backend/app backend/tests
```

The API is a contract slice, not a production deployment. Before production, the repository must be replaced or backed by approved published-release queries, with PostgreSQL/PostGIS, authentication, authorization, rate limiting, audit, migrations, and disclosure policy enforcement enabled.
