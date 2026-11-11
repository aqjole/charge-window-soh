# Partial-charge SOH estimation (Oxford Battery Degradation Dataset 1)

How much accuracy do incremental-capacity (IC) features add over a simple streaming
ΔQ estimator for battery state of health, and does the gain survive noisy, sparse
voltage logs like a real BMS produces?

Work in progress. Current state: data loader with audit, a time-based ΔQ feature on
one fixed voltage window, and mean / linear models under leave-one-cell-out
validation. The numbers in `results/` are preliminary until nested window
selection is in place.

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
