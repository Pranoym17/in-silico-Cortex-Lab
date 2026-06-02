# Cortex Lab Technical Contracts

This file resolves the implementation details that are ambiguous in the PRD. Treat it as the source of truth when scaffolding backend, frontend, inference, and tests.

## Auth Flow

1. User signs in with Supabase email auth or Google OAuth.
2. Supabase returns a JWT to the frontend.
3. Frontend attaches the token to every authenticated request:

```http
Authorization: Bearer <supabase_jwt>
```

4. FastAPI auth middleware verifies the token with `python-jose` and `SUPABASE_JWT_SECRET`.
5. Middleware extracts `sub` as the canonical external auth user ID.
6. Middleware looks up a local RDS `users` row by `supabase_user_id`.
7. If missing, middleware creates the row on first login.
8. Middleware injects the loaded user into `request.state.user`.

Auth belongs in FastAPI middleware/services, not inside route handlers and not in Celery tasks.

Supabase setup must enable:

- Email auth.
- Google OAuth.
- JWT secret copied into backend environment.

RDS `users` is separate from Supabase Auth. MVP user sync happens lazily on first authenticated API request. A Supabase webhook can be added later, but should not be required for local development.

## Run Experiment API

### `POST /api/experiments/{experiment_id}/run`

Auth required.

Request body:

```json
{
  "blocks": [
    {
      "id": "block_01HZX9E9K2M6N",
      "type": "image",
      "condition": "faces",
      "start_ms": 0,
      "duration_ms": 2000,
      "content_hash": "sha256:7f3b...",
      "s3_key": "uploads/user_123/experiments/exp_456/block_01.png",
      "mime_type": "image/png",
      "display": {
        "mode": "center"
      }
    },
    {
      "id": "block_02HZX9E9K2M6N",
      "type": "text",
      "condition": "sentences",
      "start_ms": 2000,
      "duration_ms": 8000,
      "content_hash": "sha256:b7a1...",
      "text": "The dog chased the ball.",
      "voice": "kokoro_default"
    },
    {
      "id": "block_03HZX9E9K2M6N",
      "type": "audio",
      "condition": "speech",
      "start_ms": 10000,
      "duration_ms": 30000,
      "content_hash": "sha256:fb91...",
      "s3_key": "uploads/user_123/experiments/exp_456/block_03.wav",
      "mime_type": "audio/wav",
      "channels": 1,
      "sample_rate_hz": 16000
    }
  ],
  "settings": {
    "hrf_offset_ms": 5000,
    "target_sample_rate_hz": 2,
    "surface": "fsaverage5",
    "atlas": "desikan-killiany"
  }
}
```

Response `202 Accepted`:

```json
{
  "job_id": "job_01HZXABCD123",
  "experiment_id": "exp_01HZX999",
  "status": "queued",
  "stream_url": "/api/jobs/job_01HZXABCD123/stream"
}
```

Validation failures return `422` with field-level errors.

## Stimulus Validation Rules

Experiment-level constraints:

- Maximum blocks: `50`.
- Maximum total duration: `300000 ms` / `5 min`.
- Blocks must not overlap.
- Blocks must be sorted or sortable by `start_ms`.
- `duration_ms` must be positive.
- `content_hash` is required for every block.

Image constraints:

- MIME: `image/png`, `image/jpeg`, `image/webp`.
- Max upload size: `10 MB`.
- Max decoded dimensions: `4096 x 4096`.
- Reject images with more than `16,777,216` pixels, even if the compressed file is small.
- Duration: `500 ms` to `30000 ms`.

Text constraints:

- Max words: `1024`.
- Empty or whitespace-only text is invalid.
- Duration is auto-estimated at `200 WPM` but may be overridden.
- Duration must still keep the experiment under the global cap.

Audio constraints:

- MIME: `audio/mpeg`, `audio/wav`, `audio/mp4`, `audio/x-m4a`.
- Max duration per block: `60 s`.
- Preferred inference format: mono, `16000 Hz`.
- Stereo uploads are accepted but downmixed to mono before TRIBE v2.
- Audio decode failures are validation errors before inference starts when possible.

## Job Statuses And UI Behavior

Statuses:

- `queued`: job created and waiting for worker.
- `warming`: Modal container/model is cold or loading.
- `running`: at least one block is actively processing.
- `streaming`: activation chunks are being emitted.
- `complete`: full result saved to S3.
- `failed`: terminal failure before or during inference.
- `cancelled`: user cancelled the job.

Failure classes:

- `upload_failed`: S3 upload failed before inference starts. UI returns user to builder and marks the affected block.
- `validation_failed`: backend rejected the run spec. UI opens builder with validation messages.
- `modal_oom`: TRIBE v2 OOM, usually large audio or too many generated timesteps. UI suggests shortening/compressing the stimulus.
- `timeout`: job exceeded `5 min` wall-clock runtime for MVP. UI offers retry.
- `partial_failure`: at least one chunk was streamed before crash. UI keeps partial frames visible and labels result incomplete.
- `cache_corrupt`: Redis cache payload failed checksum/decode. Backend deletes the bad key and recomputes once.
- `internal_error`: unknown server-side failure. UI shows retry and keeps diagnostic job ID.

## SSE Stream Contract

### `GET /api/jobs/{job_id}/stream?from_timestep=0`

Auth required unless the job belongs to a public shared experiment.

Use named SSE events. Each event frame is UTF-8 text. Binary activation data is encoded as base64 msgpack inside JSON, so the SSE envelope remains browser-compatible.

Event frame format:

```text
event: <event_name>
id: <monotonic_event_id>
data: <single-line-json>

```

### Event: `queued`

```text
event: queued
id: 1
data: {"job_id":"job_01HZXABCD123","status":"queued"}

```

### Event: `warming`

```text
event: warming
id: 2
data: {"job_id":"job_01HZXABCD123","reason":"modal_cold_start","estimated_seconds":90}

```

The frontend learns cold versus warm state from this event. Backend does not need to block `POST /run` by pinging Modal first.

### Event: `chunk`

The activation payload is msgpack encoded, then base64 encoded. Msgpack payload shape before base64:

```json
{
  "job_id": "job_01HZXABCD123",
  "block_id": "block_01HZX9E9K2M6N",
  "chunk_index": 0,
  "timestep_start": 0,
  "timestep_count": 1,
  "sample_rate_hz": 2,
  "vertex_count": 20000,
  "dtype": "float32",
  "shape": [1, 20000],
  "activations": "<raw float32 little-endian bytes>"
}
```

SSE JSON envelope:

```text
event: chunk
id: 3
data: {"encoding":"base64-msgpack","payload":"k6Zqb2JfaWQ..."}

```

Frontend decode path:

1. Parse SSE `data` JSON.
2. Base64-decode `payload` to bytes.
3. Msgpack-decode to object.
4. Read `activations` as little-endian `Float32Array`.
5. Apply colormap and update Three.js `geometry.attributes.color`.

### Event: `progress`

```text
event: progress
id: 4
data: {"job_id":"job_01HZXABCD123","completed_blocks":4,"total_blocks":10,"completed_timesteps":18}

```

### Event: `complete`

```text
event: complete
id: 99
data: {"job_id":"job_01HZXABCD123","status":"complete","result_s3_key":"results/job_01HZXABCD123/activations.npz","timesteps":42,"vertex_count":20000}

```

### Event: `error`

```text
event: error
id: 42
data: {"job_id":"job_01HZXABCD123","code":"partial_failure","message":"Inference crashed after 12 timesteps.","retryable":true,"last_timestep":11}

```

Reconnect behavior:

- Frontend reconnects with exponential backoff: `1s`, `2s`, `4s`, max `30s`.
- Frontend passes `from_timestep=<last_received_timestep + 1>`.
- Backend replays already persisted chunks when available.
- Zustand keeps partial chunks so the viewer does not reset.

## Celery And Modal Streaming Handshake

Celery owns job orchestration and job status. Modal owns GPU inference and cache lookup.

Checkpoint 8 starts with a deployable fake Modal provider in `inference/tribe_inference.py`. It intentionally yields the same warming/progress/chunk/complete event categories as the local fake backend path, but it does not load TRIBE v2 yet. Keep `INFERENCE_PROVIDER=fake` until backend provider wiring is explicitly switched to Modal.

Local Modal scaffold smoke test:

```bash
backend/.venv/Scripts/python inference/tribe_inference.py --smoke
```

Optional Modal deployment:

```bash
python -m pip install -r inference/requirements.txt
modal token new
modal deploy inference/tribe_inference.py
```

The backend defaults to local fake inference. To call a deployed Modal function from the backend, install the optional backend Modal client and switch the provider:

```bash
cd backend
./.venv/Scripts/python -m pip install -r requirements-modal.txt
```

```env
INFERENCE_PROVIDER=modal
MODAL_APP_NAME=cortex-lab-tribe-inference
MODAL_FUNCTION_NAME=run
```

The Modal provider consumes deployed generator events and republishes them through the same SSE contract as fake inference. Unsupported Modal event types fail the job with `internal_error`; crashes after a chunk fail with `partial_failure` so the frontend can keep partial frames visible.

Official TRIBE v2 integration constraints:

- Use `from tribev2 import TribeModel`.
- Load weights with `TribeModel.from_pretrained("facebook/tribev2", cache_folder=...)`.
- Build inputs with `model.get_events_dataframe(video_path=...)`, `audio_path=...`, or `text_path=...`.
- Predict with `preds, segments = model.predict(events=df)`.
- Treat `preds` as `(n_timesteps, n_vertices)` on the fsaverage5 cortical mesh.
- The model card documents video/audio/text naturalistic stimuli. Still image inference needs a deliberate conversion decision, such as static video generation, before it is considered scientifically acceptable.
- The text encoder requires access to the gated LLaMA 3.2-3B model, so real text inference may require a Hugging Face read token with the required access.
- The project license is CC-BY-NC-4.0, so this MVP is non-commercial unless licensing is reviewed separately.

To avoid accidental Modal GPU spend, real TRIBE mode is opt-in:

```env
TRIBE_INFERENCE_MODE=fake
```

Only set `TRIBE_INFERENCE_MODE=real` for a planned cloud smoke test.

Pseudocode:

```python
# backend/tasks/inference_task.py
@celery_app.task(bind=True)
def run_inference(self, job_id: str) -> None:
    job = load_job(job_id)
    spec = load_experiment_spec(job.experiment_id)
    mark_job(job_id, "running")

    try:
        for event in tribe_inference.run.remote_gen(spec):
            if event["type"] == "warming":
                mark_job(job_id, "warming")
                publish_sse(job_id, "warming", event)
            elif event["type"] == "chunk":
                persist_partial_chunk(job_id, event)
                publish_sse(job_id, "chunk", encode_chunk_event(event))
            elif event["type"] == "progress":
                publish_sse(job_id, "progress", event)

        result_key = write_npz_result(job_id)
        mark_job(job_id, "complete", result_s3_key=result_key)
        publish_sse(job_id, "complete", {"result_s3_key": result_key})
    except ModalOOMError as exc:
        fail_job(job_id, "modal_oom", exc)
    except TimeoutError as exc:
        fail_job(job_id, "timeout", exc)
    except Exception as exc:
        fail_job(job_id, "partial_failure" if has_partial_chunks(job_id) else "internal_error", exc)
```

```python
# inference/tribe_inference.py
@app.function(gpu="A10G", timeout=300)
def run(spec: dict):
    if model_is_loading():
        yield {"type": "warming", "reason": "modal_cold_start", "estimated_seconds": 90}

    model = load_tribe_v2()

    for block in spec["blocks"]:
        cache_key = f"tribe:v2:{block['content_hash']}"
        cached = redis_get_npz(cache_key)
        if cached is not None:
            yield chunk_from_cache(block, cached)
            continue

        activations = model(block)
        redis_set_npz(cache_key, activations, ttl_seconds=2592000)
        yield chunk_from_activations(block, activations)
```

## Redis Cache Contract

Cache keys are content-addressed and cross-user:

```text
tribe:v2:{content_hash}
```

Value:

- Compressed `.npz` bytes.
- Includes checksum metadata.
- TTL: `30 days`.

Do not include user ID, experiment ID, job ID, or S3 key in the cache key. Two users uploading identical bytes should hit the same inference cache.

## Brain Mesh And Atlas Output

`scripts/convert_mesh.py` converts FreeSurfer fsaverage5 surfaces and annotation files into frontend assets.

Output files:

```text
frontend/public/brain/fsaverage5_left.gltf
frontend/public/brain/fsaverage5_right.gltf
frontend/public/brain/atlas-desikan-killiany.json
frontend/public/brain/mesh-manifest.json
```

Left and right hemispheres are separate GLTF files to support hemisphere toggling and lower initial memory pressure.

Conversion command:

```bash
python scripts/convert_mesh.py \
  --subjects-dir /path/to/freesurfer/subjects \
  --subject fsaverage5 \
  --surface pial \
  --out frontend/public/brain
```

The converter expects these FreeSurfer files:

```text
fsaverage5/surf/lh.pial
fsaverage5/surf/rh.pial
fsaverage5/label/lh.aparc.annot
fsaverage5/label/rh.aparc.annot
```

The script uses `nibabel` to read FreeSurfer geometry/annotations and `trimesh` to export GLTF.

Until real FreeSurfer assets are available, the repo includes tiny dev fixture assets generated by:

```bash
python scripts/create_dev_brain_assets.py
```

These fixtures use the production filenames and JSON contract, but `mesh-manifest.json` has `"source": "dev-fixture"` and only 16 total vertices. Replace them by running `convert_mesh.py` when real `fsaverage5` files are available.

## Brain Viewer Contract

The viewer renders streamed activation chunks onto the fsaverage5 GLTF meshes.

Frontend responsibilities:

- Load `/brain/mesh-manifest.json`.
- Load left/right hemisphere GLTF files from `manifest.hemispheres`.
- Keep left/right activation ordering exactly as `left-then-right`.
- Select frames by global timestep using chunk `timestep_start` and `timestep_count`.
- Color vertices from float32 activation frames using the active color domain.
- Support live-follow, manual timestep scrubbing, hemisphere toggles, and auto/manual color scale.
- Preserve partial streamed chunks when a job fails or the SSE connection reconnects.

Color scale behavior:

- Auto scale uses the selected frame's min/max.
- Manual scale is valid only when both values are numeric and `min < max`.
- Invalid manual scale falls back to auto scale and shows a user-facing error.

MVP visual verification:

1. Start backend and frontend.
2. Create an experiment and run fake inference.
3. Open `/viewer/{job_id}`.
4. Confirm the canvas is nonblank and both hemispheres render.
5. Confirm chunks increment during streaming.
6. Confirm vertex colors change as timesteps arrive.
7. Confirm Pause stops live-follow, the timestep slider scrubs previous frames, and Live jumps to the newest frame.
8. Confirm left/right toggles never hide both hemispheres at once.
9. Confirm manual color scale changes the displayed colors and invalid min/max shows an error.

The repo intentionally does not add Playwright for MVP CI yet. Browser screenshot and canvas-pixel checks should be added when frontend visual regressions become frequent enough to justify the extra dependency and runtime.

Required GLTF vertex attributes:

- `POSITION`: float32 xyz.
- `NORMAL`: float32 xyz.
- `COLOR_0`: float32 RGB, initialized to neutral gray.

Vertex ordering must match TRIBE v2 output ordering:

- Left hemisphere vertices first.
- Right hemisphere vertices second.
- No reindexing after FreeSurfer load unless the same mapping is written to the manifest.

Atlas JSON shape:

```json
{
  "0": "Left-Banks-STS",
  "1": "Left-Caudal-ACC",
  "10242": "Right-Banks-STS"
}
```

Manifest shape:

```json
{
  "surface": "fsaverage5",
  "vertex_count": 20484,
  "left_vertex_count": 10242,
  "right_vertex_count": 10242,
  "ordering": "left-then-right",
  "atlas": "desikan-killiany",
  "gltf": {
    "left": "/brain/fsaverage5_left.gltf",
    "right": "/brain/fsaverage5_right.gltf"
  },
  "hemispheres": {
    "left": {
      "file": "/brain/fsaverage5_left.gltf",
      "vertex_count": 10242,
      "activation_offset": 0
    },
    "right": {
      "file": "/brain/fsaverage5_right.gltf",
      "vertex_count": 10242,
      "activation_offset": 10242
    }
  }
}
```

## Local Development Setup

Required local sequence:

1. Copy `.env.example` to `.env` and fill backend values.
2. Copy `frontend/.env.example` to `frontend/.env.local` and fill frontend values.
3. Smoke-check the Modal inference scaffold:

```bash
backend/.venv/Scripts/python inference/tribe_inference.py --smoke
```

4. Optional: create/authenticate Modal credentials when Checkpoint 8 provider wiring is ready:

```bash
modal token new
```

5. Optional: deploy the Modal scaffold:

```bash
modal deploy inference/tribe_inference.py
```

6. Start local infrastructure:

```bash
docker-compose up
```

7. Apply backend migrations:

```bash
cd backend
alembic upgrade head
```

8. Start frontend:

```bash
cd frontend
npm install
npm run dev
```

For the future scaffold, `docker-compose` should include Postgres, Redis, FastAPI, Celery worker, and any local SQS substitute needed for development.

## Cost Envelope

Estimated MVP monthly cost at low traffic:

| Component | Estimate |
| --- | ---: |
| RDS `t3.micro` | `$13` |
| ECS Fargate API + worker | `$15-25` |
| Modal GPU, 100 inferences at ~10s | `~$2` |
| S3 + CloudFront | `$1-3` |
| Upstash Redis | Free tier |
| Supabase Auth | Free tier |
| Total MVP | `~$35/mo` |

## Testing Strategy

Backend:

- `pytest`.
- `httpx.AsyncClient` for FastAPI route tests.
- Mock Modal calls and S3.
- Test auth middleware separately from route handlers.
- Test validation rules for each stimulus type.
- Test SSE event encoding with a known float32 fixture.

Frontend:

- `Vitest`.
- Store and utility tests for experiment builder state, viewer state, SSE decoding, colormap mapping, and auth token attachment.
- No Playwright in MVP CI unless a browser regression becomes costly.

CI:

- GitHub Actions runs backend `pytest`.
- GitHub Actions runs frontend `vitest`.
- CI should fail on type errors, lint errors, and contract fixture mismatches.
