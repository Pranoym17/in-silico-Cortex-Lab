# TRIBE Live-Proof Harness

This harness invokes a deployed Modal generator and writes a sanitized evidence
report. It never stores activation bytes, tokens, authorization values, or
environment variables. Generated reports live under the ignored `evidence/`
directory.

## Prerequisites

1. Deploy `inference/tribe_inference.py` with the real runtime and Hugging Face
   secret configured.
2. Authenticate the local Modal client.
3. Create a JSON run specification containing short, licensed stimuli. Media
   blocks must use S3 objects that the deployed function can read.

## Run

From the repository root:

```powershell
.\inference\.venv\Scripts\python.exe scripts\prove_tribe_live.py `
  --spec evidence-inputs\short-text.json `
  --app cortex-lab-tribe-inference `
  --function run_real
```

To include an approximate cost, pass the current A10G hourly price you intend
to use for planning:

```powershell
.\inference\.venv\Scripts\python.exe scripts\prove_tribe_live.py `
  --spec evidence-inputs\short-text.json `
  --gpu-hourly-usd 1.10
```

The cost is explicitly a wall-clock estimate. Confirm billed GPU usage and
current pricing in the Modal dashboard.

Use separate specifications for text, uploaded audio, microphone WebM, and
image-derived video. Never put provider credentials in a specification.

## Acceptance Checks

The command exits zero only when:

- at least one chunk is present and every chunk has 20,484 float32 vertices;
- activation byte length agrees with the reported shape;
- one positive, consistent sample rate is reported;
- every stimulus metadata event reports a five-second HRF offset;
- all word timings are structurally valid and text blocks have timings;
- exactly one successful completion event exists and no error event exists.

The report also records warming-to-first-chunk, invocation-to-first-chunk,
total wall-clock duration, and estimated GPU seconds. Event timestamps are
observed client-side and therefore include network latency.

## Evidence Handling

Reports are ignored by Git because operational evidence can contain stimulus
identifiers and infrastructure details. Review each report before sharing it.
Commit only a separately reviewed, manually redacted benchmark summary.

Run unit tests with:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests\test_tribe_live_proof.py
```
