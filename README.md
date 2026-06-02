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

To let the local backend call the deployed Modal function, install the optional Modal client dependency in the backend venv and switch providers:

```bash
cd backend
./.venv/Scripts/python -m pip install -r requirements-modal.txt
```

```env
INFERENCE_PROVIDER=modal
MODAL_APP_NAME=cortex-lab-tribe-inference
MODAL_FUNCTION_NAME=run
```

Leave `INFERENCE_PROVIDER=fake` for normal local development unless you are intentionally testing cloud inference.

Real TRIBE v2 mode is also opt-in. The official model card loads the model with `TribeModel.from_pretrained("facebook/tribev2")`, builds events with `model.get_events_dataframe(...)`, and predicts `(n_timesteps, n_vertices)` with `model.predict(events=df)`. Keep this disabled unless you are ready for a planned Modal smoke test:

```env
TRIBE_INFERENCE_MODE=fake
TRIBE_CACHE_FOLDER=./cache
TRIBE_CHUNK_TIMESTEPS=4
TRIBE_EXPECTED_VERTEX_COUNT=
HF_TOKEN=
```

For real text inference, Hugging Face access to the gated LLaMA 3.2-3B dependency may be required. Do not set `TRIBE_INFERENCE_MODE=real` casually; real mode can trigger model downloads and Modal GPU time.

Real audio/video inference uses TRIBE's official `audio_path` and `video_path` inputs. If the run spec contains S3 keys, the Modal function downloads those objects only after `TRIBE_INFERENCE_MODE=real` is enabled. Image blocks remain fake-only until we choose a scientifically acceptable conversion path, because the official TRIBE v2 card documents video/audio/text inputs rather than still images.

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
