# Partial-charge SOH estimation (Oxford Battery Degradation Dataset 1)

How much accuracy do incremental-capacity (IC) features add over a simple streaming
ΔQ estimator for battery state of health, and does the gain survive noisy, sparse
voltage logs like a real BMS produces?

Work in progress. Current state: data loader with audit, a streaming-style window
detector (arming band, time-below-level crossings, sample-gap check) with every "no estimate"
counted by reason, a time-based ΔQ feature, incremental-capacity (IC) peak
features, and six models under nested leave-one-cell-out validation: M0 mean,
M1 linear(ΔQ), M2 linear(ΔQ + IC peak), M3 GPR(ΔQ), M4 GPR(ΔQ + IC peak), M5
GPR(ΔQ of each half of the window), and a streaming C version of M1 checked
against Python. Each model picks its voltage window inside each outer fold using only the 7 training
cells. Tables are in `results/clean_nested.md` (pooled, with GPR 95 % coverage and
interval width, raw and calibrated), `results/clean_nested_per_cell.md`, `results/window_log.md` and
`results/paired.md` (each model vs its control on commonly answered traces, with
the decision rule: M2 vs M1 and M4 vs M3 for the IC peak, M5 vs M3 for the split). `results/predictions_gpr.png` shows the held-out GPR errors with
their calibrated 95 % bands.

Known limitation of the IC features: settings (5 mV bins, Savitzky-Golay 7 bins,
order 2) were frozen before the first run with IC. For windows starting at 3.8 V,
early-life traces lose their IC estimate partly because the dQ/dV peak (~3.82 V)
sits within the smoothing half-width of the window edge. As a result the IC models
have no 100 mV window that answers 95 % of traces; that row is reported as not
available.

Two-segment ΔQ (M5): the window is split at its midpoint voltage and the GPR gets
both halves' ΔQ, a coarse view of curve shape that needs no differentiation. Clean
RMSE 0.41 SOH points against 0.45 for M3 and 0.31 for M4; better than M3 on 6 of
8 cells, short of the 7-of-8 rule, so no detectable gain. At 300 mV width it is
unstable (one cell misses by up to 18 points). Its value shows in the degraded logs.

GPR intervals: the raw 95 % intervals cover 87 % (M3), 92 % (M4) and 92 % (M5)
of held-out measurements, because they reflect noise within the training cells,
not the spread between cells. Each fold therefore also reports calibrated
intervals: the std is scaled by k, the 95th percentile of |error| / std on the
inner held-out cells (training cells only) divided by 1.96; k is 1.06-1.57. This
reuses the inner fits and lifts pooled coverage to 91 % (M3), 95 % (M4) and 97 %
(M5), at 1.1-1.9 SOH points mean width. It fixes the average, not single cells
whose error drifts with age: cell 7 stays at 68 % (M3) and 77 % (M4), cell 4 at
72 % (M3). `results/predictions_gpr.png` shows the calibrated bands.

Window detector: the window starts and ends where the time spent below V1 and below
V2 says it does (time-below-level), not at the first sample that crosses each level.
On a clean, rising trace the two are identical. With noise, a first-crossing rule
fires early by roughly sigma / (dV/dt), worst where the charge curve is flat
(3.8-3.9 V); time-below-level averages the repeated crossings instead. It needs two
running sums and no sample buffer, so it suits a streaming C estimator.

Degraded-log tests (`results/degraded.md`, `results/degraded_paired.md`,
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
  M4 (92 % clean, 42 % at 5 mV). Calibration, set on clean data, does not repair
  this: calibrated M4 covers 49 % at 5 mV, and M3 and M5 drop to 53-66 %
  under a ±5 mV offset.
- M5 keeps part of what curve shape adds where the IC peak breaks down: 0.47 at
  5 mV noise (M4 1.04), 0.57 at a 5 mV ADC step (M4 0.78), 0.41-0.42 at 30-60 s
  logging (M4 0.66, then no answer). Like every ΔQ model it is offset-sensitive
  (0.93-1.03 at ±5 mV, where the IC models stay at 0.30-0.56).

C estimator (`c/`): a streaming M1 in C99, double precision, no heap; it keeps two
time-below accumulators and the previous sample. The deployable model is frozen by
`python -m soh.freeze` with the same window rule, now over all 8 cells. It picks
3.8-4.0 V (selection score 0.575 SOH points, against 0.578 for 3.5-3.9 V and
3.8-4.1 V, so the top three are nearly tied), then fits M1 on all 8 cells:
C [mAh] = 91.93 + 1.987 · ΔQ [mAh] (`results/frozen.md`). The exact coefficients
go into the generated `c/soh_model.h`. The selection score is computed on the cells
that chose the window, so the accuracy to quote is still the nested one above.
`build/replay` streams exported traces through the C code: on all 519 clean traces
and on seed 0 of the combined degraded case it returns the same reason codes as the
Python reference and SOH within 1e-14 (gate 1e-4), see `results/c_agreement.md`.
`make test` also checks the C code against the Python detector on synthetic traces
(noise, 1 mV quantization, gaps, dips, every reason code) without the dataset.

`make reproduce` takes 10-40 minutes on an 8-core laptop, depending on load; nearly all of it
is about 1,450 GPR fits in the validation, run in parallel.

## Data

Oxford Battery Degradation Dataset 1, DOI
[10.5287/bodleian:KO2kdmYGg](https://doi.org/10.5287/bodleian:KO2kdmYGg):
8 Kokam 740 mAh pouch cells cycled at 40 °C, characterized every 100 cycles.
`make data` downloads the .mat file (about 254 MB) to `data/raw/`; it is not
committed. The loader checks its SHA-256.

## Reproduce

Requires [uv](https://docs.astral.sh/uv/), Python 3.11 and a C99 compiler.

```bash
make reproduce
```

This creates `.venv` from the pinned `requirements.txt`, runs the tests, runs the
data audit (`results/audit.md`, `results/capacity_fade.png`), writes the
validation and degraded-log tables to `results/`, freezes M1 into `c/soh_model.h`,
builds `build/replay` and checks it against the Python reference. `make agree` runs
only the last three steps.
