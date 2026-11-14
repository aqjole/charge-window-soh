# Partial-charge SOH estimation (Oxford Battery Degradation Dataset 1)

How much accuracy do incremental-capacity (IC) features add over a simple streaming
ΔQ estimator for battery state of health, and does the gain survive noisy, sparse
voltage logs like a real BMS produces?

Work in progress. Current state: data loader with audit, a streaming-style window
detector (arming band, time-below-level crossings, sample-gap check) with every "no estimate"
counted by reason, a time-based ΔQ feature, incremental-capacity (IC) peak
features, and five models under nested leave-one-cell-out validation: M0 mean,
M1 linear(ΔQ), M2 linear(ΔQ + IC peak), M3 GPR(ΔQ), M4 GPR(ΔQ + IC peak). Each
model picks its voltage window inside each outer fold using only the 7 training
cells. Tables are in `results/clean_nested.md` (pooled, with GPR 95 % coverage and
interval width), `results/clean_nested_per_cell.md`, `results/window_log.md` and
`results/paired_ic.md` (IC model vs its control on commonly answered traces, with
the decision rule). `results/predictions_gpr.png` shows the held-out GPR errors with
their 95 % bands.

Known limitation of the IC features: settings (5 mV bins, Savitzky-Golay 7 bins,
order 2) were frozen before the first run with IC. For windows starting at 3.8 V,
early-life traces lose their IC estimate partly because the dQ/dV peak (~3.82 V)
sits within the smoothing half-width of the window edge. As a result the IC models
have no 100 mV window that answers 95 % of traces; that row is reported as not
available.

Known limitation of the GPR intervals: pooled 95 % coverage on held-out cells is
87 % (M3) and 92 % (M4), below nominal. The shortfall is concentrated in cells 4
and 7, whose error drifts with age: the intervals reflect noise within the training
cells, not the spread between cells.

Window detector: the window starts and ends where the time spent below V1 and below
V2 says it does (time-below-level), not at the first sample that crosses each level.
On a clean, rising trace the two are identical. With noise, a first-crossing rule
fires early by roughly sigma / (dV/dt), worst where the charge curve is flat
(3.8-3.9 V); time-below-level averages the repeated crossings instead. It needs two
running sums and no sample buffer, so it suits a streaming C estimator.

Degraded-log tests (`results/degraded.md`, `results/degraded_paired_ic.md`,
`results/degraded.png`): each outer fold's frozen model is applied to copies of its
held-out cell with voltage noise, offset, ADC quantization or a longer sample period.
Each case also runs with the old first-crossing detector as a baseline. Main
findings so far:

- With time-below-level, noise barely moves the ΔQ models: M1 goes 0.67 -> 0.69
  SOH points at 2 mV and 0.84 at 10 mV (first-crossing: 1.15 and 4.26). M3 stays
  at 0.46-0.54.
- The IC peak itself is noise-sensitive, so the IC models now degrade faster than
  their ΔQ partners. IC no longer helps under 5 mV noise or more, and the GPR IC
  model (M4) shows no detectable gain over M3 at any noise level.
- A constant voltage offset shifts the levels themselves; no detector can remove it.
  It is now the main weakness of the ΔQ models (M1 0.67 -> 1.36-1.41 at ±5 mV).
- A longer sample period does not hurt ΔQ, but it starves the IC features: at 60 s
  every trace is IC_SPARSE and M2/M4 give no estimate.
- GPR coverage holds for M3 under noise (87 % clean, 86 % at 5 mV) but falls for
  M4 (92 % clean, 42 % at 5 mV).

`make reproduce` takes 7-30 minutes on an 8-core laptop, depending on load; nearly all of it is
about 950 GPR fits in the validation, run in parallel.

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
