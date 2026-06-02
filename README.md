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

Provide a PostgreSQL database before running migrations. Docker is optional; a hosted Postgres database or a normal Windows PostgreSQL install works too.

Set `DATABASE_URL` in `.env`:

```env
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/DB_NAME
```

Then apply migrations:

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

Smoke-check the Modal/TRIBE scaffold without deploying anything:

```bash
backend/.venv/Scripts/python inference/tribe_inference.py --smoke
```

Deploying the scaffold to Modal is optional until Checkpoint 8 provider wiring is enabled. When you are ready, install the inference requirements, authenticate Modal, then deploy:

```bash
python -m pip install -r inference/requirements.txt
modal token new
modal deploy inference/tribe_inference.py
```

Smoke-check the brain viewer:

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000/viewer/<job_id>` after creating a fake run. The viewer should render both hemispheres, stream activation colors onto the mesh, support pause/live playback, scrub timesteps, toggle hemispheres, and adjust the color scale.

Optional Docker flow, if Docker Desktop is working:

```bash
docker compose up postgres redis
```

Start the frontend dev server:

```bash
cd frontend
npm run dev
```
