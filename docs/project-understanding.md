# Cortex Lab Project Understanding

Cortex Lab is a browser-based in-silico neuroscience platform. Users create multimodal experiments, run them through Meta TRIBE v2 on GPU infrastructure, and inspect predicted fMRI activations on an interactive fsaverage5 cortical surface.

The MVP is not just a model demo. It is an end-to-end research workflow:

- Build experiments from image, text, and audio stimulus blocks.
- Upload large media directly to S3 via presigned URLs.
- Run asynchronous inference through FastAPI, Celery/SQS, and Modal.
- Stream activation chunks back to the browser as they finish.
- Render approximately 20,000 cortical vertex activations with React Three Fiber.
- Add scientific interpretation through atlas lookup, region timecourses, cognitive state labels, RSA, and later optimization.

## Primary Architecture

The core path is:

1. Supabase signs the user in and returns a JWT.
2. Frontend sends `Authorization: Bearer <token>` on every authenticated API request.
3. FastAPI middleware verifies the JWT with `SUPABASE_JWT_SECRET`, extracts the `sub` claim, upserts/loads the corresponding RDS user, and attaches it to `request.state.user`.
4. User creates or edits an experiment in the builder.
5. Media files are uploaded directly to S3 through presigned URLs. The API stores metadata and S3 object references, not raw file bytes.
6. User runs the experiment with `POST /api/experiments/{id}/run`.
7. FastAPI validates the full stimulus spec, creates a queued job row, enqueues Celery work, and returns a job ID immediately.
8. Frontend opens `GET /api/jobs/{id}/stream`.
9. Celery calls a Modal GPU generator function.
10. Modal loads or reuses TRIBE v2, checks the content-addressed Redis cache, runs missing blocks, and yields activation chunks.
11. Celery publishes each chunk to the job stream.
12. FastAPI emits SSE events to the browser.
13. Frontend decodes the event payload, updates vertex color buffers, and stores partial progress for reconnects.
14. On completion, the full activation matrix is written to S3 as compressed `.npz`, and the RDS job row becomes `complete`.

## Implementation Priorities

The hardest parts should be specified before coding:

- Exact run request/response schemas.
- Exact SSE event names and binary payload encoding.
- Supabase-to-FastAPI auth boundary.
- Celery-to-Modal streaming handshake.
- Redis cache key format.
- Stimulus validation constraints.
- Cold start and partial failure UX.
- fsaverage5 GLTF and atlas output format.
- Local development setup.
- Testing strategy.

These details live in [technical-contracts.md](technical-contracts.md).

## Product Surfaces

- **Dashboard:** authenticated user experiment list.
- **Builder:** dnd-kit timeline for image, text, and audio blocks.
- **Viewer:** Three.js/R3F cortical surface, timeline scrubber, streaming updates, atlas tooltips, region spotlight, charts.
- **Paradigm Library:** published experiments with blocks and metadata that can be browsed publicly and forked into user experiments.
- **ML Suite:** cognitive state classifier, RSA comparison, stimulus optimizer.

## Non-Goals For The First Scaffold

- Do not start with the full ML suite.
- Do not hand-roll auth separate from Supabase.
- Do not route image/audio bytes through FastAPI.
- Do not make the activation stream JSON arrays of 20,000 floats unless using a temporary dev-only path.
- Do not user-scope the Redis inference cache. Cache keys must be content-addressed so identical stimuli dedupe across users.

