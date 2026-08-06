# Cortex Lab

Browser-based platform for in-silico neuroscience: design experiments, run them through Meta's TRIBE v2 brain model, and explore predicted fMRI activations on an interactive 3D cortical surface. No scanner required.

> Cortex Lab displays model predictions for an average synthetic subject. Outputs are not measured fMRI, medical advice, diagnosis, or evidence about an individual.

This is an active research-platform implementation. Internal planning, operational notes, and validation records are intentionally kept out of the public repository.

## MVP Stack

- Frontend: Next.js, TypeScript, React Three Fiber, Zustand, TanStack Query.
- Backend: FastAPI, Python 3.11, Celery, PostgreSQL/RDS, Redis, S3, SQS.
- Inference: Modal GPU functions running TRIBE v2.
- Auth: Supabase Auth JWT verified by FastAPI middleware.
- Visualization: fsaverage5 GLTF cortical meshes with per-vertex activation colors.

## Local Setup

Environment ownership is deliberate:

- Root `.env`: FastAPI, background worker, Docker, database, Redis, S3, Modal, and server-only secrets.
- `frontend/.env.local`: only `NEXT_PUBLIC_*` browser configuration.
- There is no `backend/.env`; backend settings always load the root `.env`.

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

Start the background worker in a second terminal. On native Windows, Celery's
default prefork pool cannot reliably use its multiprocessing locks, so use the
single-process `solo` pool:

```powershell
cd backend
.\.venv\Scripts\celery.exe -A app.tasks.celery_app.celery_app worker --loglevel=INFO --pool=solo --concurrency=1
```

This processes one job at a time locally and is the expected development setup.
The Docker worker runs on Linux and keeps the default multiprocessing pool.

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

The deployed Modal app exposes two inference entrypoints. `run` stays lightweight and fake. `run_real` uses the real TRIBE image and should only be selected for planned cloud tests:

```env
MODAL_FUNCTION_NAME=run
MODAL_HF_SECRET_NAME=huggingface-secret
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

For real text inference, Hugging Face access to the gated LLaMA 3.2-3B dependency may be required. Do not set `TRIBE_INFERENCE_MODE=real` casually; real mode can trigger model downloads and Modal GPU time. The installable official source repository is `https://github.com/facebookresearch/tribev2`; the Hugging Face `facebook/tribev2` repository is the model/weights repository, not the editable Python package source.

Local TRIBE source validation can live outside this repository:

```bash
cd "C:\Users\Pranoy\Cortex Lab"
git clone https://github.com/facebookresearch/tribev2 tribe-v2-source
cd tribe-v2-source
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pip install "exca==0.5.20"
.\.venv\Scripts\python.exe -c "from tribev2 import TribeModel; print('tribev2 import ok')"
```
```bash
.\inference\.venv\Scripts\modal.exe secret create huggingface-secret HF_TOKEN=hf_your_new_read_token
```

Then deploy the app. This creates both `run` and `run_real`, but it does not run real inference:

```bash
.\inference\.venv\Scripts\modal.exe deploy inference\tribe_inference.py
```

Real audio/video inference uses TRIBE's official `audio_path` and `video_path` inputs. If the run spec contains S3 keys, the Modal function downloads those objects only after `TRIBE_INFERENCE_MODE=real` is enabled. Image blocks are converted into constant-frame MP4 clips for their configured duration and then use the official `video_path` pipeline. The production Modal image enforces the fsaverage5 output size of 20,484 vertices.

TRIBE's current official text pipeline performs text-to-speech with gTTS and transcribes the generated audio to obtain word timings. Result metadata records those timings, the model segment count, the actual prediction sample rate derived from TRIBE's repetition time, and the documented five-second HRF offset.

Check real TRIBE readiness without loading model weights or running GPU:

```bash
backend/.venv/Scripts/python inference/tribe_inference.py --check-real-config
```

If real mode is enabled before setup is complete, the Modal function emits a `tribe_not_ready` error event instead of loading weights.

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
