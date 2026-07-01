# Scientific Validation

Cortex Lab displays predictions from TRIBE v2 for an average synthetic subject. Results are not measured fMRI, medical advice, diagnosis, or evidence about an individual.

## Temporal Contract

Real inference processes each block independently and concatenates its output rows. Every result therefore stores a `stimuli` mapping with:

- experiment start and duration;
- output timestep start and count;
- actual model sample rate;
- five-second HRF offset;
- alignment policy `concatenated-block-output-v1`.

Viewer and analysis code must use this mapping instead of deriving rows from experiment milliseconds. Legacy results without the mapping use the documented fallback and should not be used as scientific reference fixtures.

## Spatial Contract

- Surface: fsaverage5.
- Vertices: 20,484.
- Ordering: 10,242 left-hemisphere vertices followed by 10,242 right-hemisphere vertices.
- Atlas: Desikan-Killiany labels projected onto the exact checked-in mesh coordinates.

The structural contract is necessary but not sufficient. Real reference runs must also pass expected-region landmark checks.

## Reference Runs

Generate one short, licensed real-TRIBE fixture for each class:

- visual: lateral occipital, pericalcarine, lingual, or cuneus;
- auditory: superior temporal or transverse temporal;
- language: pars opercularis, pars triangularis, or superior temporal;
- faces: fusiform.

Run:

```powershell
backend\.venv\Scripts\python.exe scripts\validate_scientific_output.py `
  evidence\reference\faces.npz `
  --stimulus-class faces
```

The report hashes the fixture, validates matrix and mesh contracts, and records the expected-region activation percentile. The default 60th-percentile threshold is an engineering smoke criterion, not a published scientific effect-size threshold. A neuroscience reviewer must approve reference stimuli and acceptance thresholds before external scientific claims.

## RSA Reference

The test suite compares Cortex Lab's tie-aware Spearman implementation against `scipy.stats.spearmanr`. RSA still depends on valid block-to-output mappings and comparable experiment design.
