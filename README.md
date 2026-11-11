# Partial-charge SOH estimation (Oxford Battery Degradation Dataset 1)

How much accuracy do incremental-capacity (IC) features add over a simple streaming
ΔQ estimator for battery state of health, and does the gain survive noisy, sparse
voltage logs like a real BMS produces?

Work in progress. Current state: data loader with audit, a streaming-style window
detector (arming band, first crossing, sample-gap check) with every "no estimate"
counted by reason, a time-based ΔQ feature, and mean / linear models under nested
leave-one-cell-out validation: each model picks its voltage window inside each
outer fold using only the 7 training cells. Tables are in `results/clean_nested.md`
(pooled), `results/clean_nested_per_cell.md` and `results/window_log.md`.

## Data

Oxford Battery Degradation Dataset 1, DOI
[10.5287/bodleian:KO2kdmYGg](https://doi.org/10.5287/bodleian:KO2kdmYGg):
8 Kokam 740 mAh pouch cells cycled at 40 °C, characterized every 100 cycles.
`make data` downloads the .mat file (about 254 MB) to `data/raw/`; it is not
committed. The loader checks its SHA-256.

## Reproduce

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11.

```bash
make reproduce
```

This creates `.venv` from the pinned `requirements.txt`, runs the tests, runs the
data audit (`results/audit.md`, `results/capacity_fade.png`) and writes the
validation tables to `results/`.
