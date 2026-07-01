# Stimulus Library

The launch catalog contains 204 first-party generated assets:

- 40 schematic faces;
- 40 scenes, including 20 houses;
- 40 geometric objects;
- 40 rendered-word images;
- 40 abstract patterns;
- 4 instrumental/control WAV files.

The generator and every output are dedicated under CC0 1.0. The manifest records creator, source, license, attribution text, MIME type, S3 key, and SHA-256 hash. Schematic faces depict no real person and avoid identity or personality-right claims.

These are engineering/demo stimuli. They do not establish replication of a published neuroscience effect. Stronger scientific claims require reviewed reference datasets and the process in `scientific-validation.md`.

## Rebuild

```powershell
backend\.venv\Scripts\python.exe scripts\generate_stimulus_catalog.py
```

The catalog test verifies all files and hashes.

## Upload

After confirming the target AWS account and bucket:

```powershell
backend\.venv\Scripts\python.exe scripts\sync_stimulus_catalog.py --dry-run
backend\.venv\Scripts\python.exe scripts\sync_stimulus_catalog.py
```

The uploader writes hash/license metadata and verifies every uploaded object. CloudFront should expose the same object prefix after S3 synchronization.

## Launch Paradigms

The builder includes:

1. FFA face versus house
2. N400 congruency
3. Visual eccentricity
4. Emotion processing
5. Speech versus music
6. Reading versus listening

Every block includes a content hash. Image/audio blocks reference deterministic `stimulus-library/v1/` S3 keys and display their attribution in the catalog browser.
