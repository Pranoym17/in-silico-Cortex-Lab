# Cortex Lab

Browser-based platform for in-silico neuroscience: design experiments, run them through Meta's TRIBE v2 brain model, and explore predicted fMRI activations on an interactive 3D cortical surface. No scanner required.

This repository is currently in the specification stage. The PRD defines the product vision; the docs in this repo pin down the implementation contracts that code should follow.

## Source Of Truth

- [Project understanding](docs/project-understanding.md): product shape, architecture, implementation priorities, and non-goals.
- [Technical contracts](docs/technical-contracts.md): auth flow, run API schema, SSE wire format, Celery/Modal handshake, validation rules, cache keys, mesh outputs, setup, costs, and tests.

## MVP Stack

- Frontend: Next.js, TypeScript, React Three Fiber, Zustand, TanStack Query.
- Backend: FastAPI, Python 3.11, Celery, PostgreSQL/RDS, Redis, S3, SQS.
- Inference: Modal GPU functions running TRIBE v2.
- Auth: Supabase Auth JWT verified by FastAPI middleware.
- Visualization: fsaverage5 GLTF cortical meshes with per-vertex activation colors.

## Local Setup

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env.local
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements-dev.txt
cd frontend
npm install
cd ..
```

Start Postgres and Redis before running migrations:

```bash
docker compose up postgres redis
```

In a second terminal, apply migrations:

```bash
cd backend
../.venv/Scripts/python -m alembic upgrade head
cd ..
```

Supabase is optional until the real login flow is exercised. When your Supabase project exists, fill in `frontend/.env.local` with `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`, then put the matching `SUPABASE_JWT_SECRET` in `.env`.

Run backend tests:

```bash
$env:PYTHONPATH="backend"
.venv/Scripts/python -m pytest backend/tests --basetemp=.tmp_pytest -p no:cacheprovider
```

Run DB-backed integration tests after Postgres is running and migrations are applied:

```bash
$env:PYTHONPATH="backend"
$env:CORTEX_RUN_DB_TESTS="1"
.venv/Scripts/python -m pytest backend/tests --basetemp=.tmp_pytest -p no:cacheprovider
```

Run frontend checks:

```bash
cd frontend
npm test
npm run build
```

Start local services:

```bash
docker compose up
```

Start the frontend dev server:

```bash
cd frontend
npm run dev
```
