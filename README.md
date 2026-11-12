# Partial-charge SOH estimation (Oxford Battery Degradation Dataset 1)

How much accuracy do incremental-capacity (IC) features add over a simple streaming
ΔQ estimator for battery state of health, and does the gain survive noisy, sparse
voltage logs like a real BMS produces?

Work in progress. Current state: data loader with audit, a streaming-style window
detector (arming band, first crossing, sample-gap check) with every "no estimate"
counted by reason, a time-based ΔQ feature, incremental-capacity (IC) peak
features, and mean / linear models (M0, M1 = ΔQ, M2 = ΔQ + IC peak) under nested
leave-one-cell-out validation: each model picks its voltage window inside each
outer fold using only the 7 training cells. Tables are in `results/clean_nested.md`
(pooled), `results/clean_nested_per_cell.md`, `results/window_log.md` and
`results/paired_ic.md` (M2 vs M1 on commonly answered traces, with the decision rule).

Known limitation of the IC features: settings (5 mV bins, Savitzky-Golay 7 bins,
order 2) were frozen before the first run with IC. For windows starting at 3.8 V,
early-life traces lose their IC estimate partly because the dQ/dV peak (~3.82 V)
sits within the smoothing half-width of the window edge. As a result M2 has no
100 mV window that answers 95 % of traces; that row is reported as not available.

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
