# External Services And Licensing Decisions

This document is the Section 0 release gate. Do not enable real inference in staging or production until:

```powershell
python scripts/check_external_readiness.py --strict
```

reports `READY`. The checker reports presence and consistency only; it never prints secret values.

## Decisions

- **Production region:** `ca-central-1` is the default because the project owner is in Canada. Change it only through an explicit architecture decision after checking service availability, latency, residency, and cost.
- **Modal:** local development stays on the fake provider. Staging uses the deployed `run_real` function only after `MODAL_GPU_TESTS_APPROVED=true` and `MODAL_GPU_BUDGET_USD` is positive.
- **Hugging Face:** use a separate fine-grained, read-only application token with access to `facebook/tribev2` and every gated dependency required by TRIBE.
- **Supabase:** use separate staging and production projects. Configure exact production redirect URLs, magic-link templates, Google OAuth credentials, and matching backend/frontend project URLs.
- **Stimulus assets:** bundled assets are restricted to verified CC0 or public-domain material. Every file must have an attribution-manifest entry even when attribution is not legally required. Wikimedia Commons may be used only after verifying the individual file page; Freesound imports must be CC0.
- **TRIBE license:** TRIBE v2 is CC BY-NC 4.0. Cortex Lab therefore operates in `research-noncommercial` mode. Do not sell TRIBE inference, bundle it into a paid plan, or represent commercial use as approved without a separate commercial license or written legal approval.

These are engineering controls, not legal advice.

## User-Owned Setup

### Modal

1. Create or select a Modal workspace.
2. Run `inference\.venv\Scripts\modal.exe token new`, or create a service-user token for deployment.
3. Put `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` in the uncommitted `.env`.
4. Create the Hugging Face Modal secret:

```powershell
inference\.venv\Scripts\modal.exe secret create huggingface-secret HF_TOKEN=hf_your_token
```

### Hugging Face

1. Accept access terms for `facebook/tribev2` and its gated dependencies.
2. Create a dedicated fine-grained read token.
3. Store it only in `.env` and the Modal secret.

### AWS

1. Confirm `ca-central-1` or record a replacement region decision.
2. Use a least-privilege deployment identity; do not use root credentials.
3. Configure the bucket, queue, Redis endpoint, and production database before live proof runs.

### Supabase

1. Create separate staging and production projects.
2. Enable magic link and Google OAuth.
3. Set the exact Site URL and callback allowlist.
4. Configure matching backend and frontend values.

### GPU Cost Approval

Set a hard test budget before any real deployment:

```env
MODAL_GPU_TESTS_APPROVED=true
MODAL_GPU_BUDGET_USD=25
```

This approves tests only up to the stated budget; it is not authorization for unattended production spending.
