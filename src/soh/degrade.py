"""Degraded-log tests: frozen fold models applied to BMS-like versions of the held-out cell.

Estimators are each outer fold's trained model at the window that fold selected in
the any-width regime (read from `results/window_log.csv`), refit on the clean
training cells (M6 also on their offset copies) and then frozen. Each is applied
only to its fold's held-out cell; the final all-cells model is never used here.

Per trace, in this order:
1. decimate to `period_s` by sample-and-hold on a logger clock with a random phase
   (the last native sample at or before each tick is kept, with its own time stamp);
2. add a constant offset and Gaussian noise;
3. round to the ADC LSB.
Window detection and feature extraction then run on the degraded trace.

Randomness is per trace, from `default_rng([seed, cell, cycle])`, so a result does
not depend on processing order and every case sees the same random numbers for the
same seed. Cases with nothing random run once (seed 0).

Every case runs twice: with the project's window detector (time-below-level) and,
as a baseline, with the first-crossing rule used up to commit 6. The baseline's
fold models are refit on clean first-crossing features at the same windows, so the
two rows differ only in the detector.

Calibrated GPR intervals use each fold's k95 from the clean inner fits (window log),
for the main detector only.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from soh import plots
from soh.features import detect_first_crossing, detect_window
from soh.load import Curve, load
from soh.models import MODELS, PAIRS
from soh.report import RESULTS, write_table
from soh.validate import HELPS, HELPS_MIN_CELLS, Win, feature_row, feature_table, fit_model, metrics, paired, predict_rows

NATIVE_PERIOD_S = 1.0
SEEDS = tuple(range(20))
REGIME = "any"
DETECTORS = {"time-below": detect_window, "first-crossing": detect_first_crossing}
MAIN_DETECTOR = "time-below"


@dataclass(frozen=True)
class Case:
    name: str
    factor: str
    noise_mv: float = 0.0
    offset_mv: float = 0.0
    lsb_mv: float = 0.0  # 0: no rounding
    period_s: float = NATIVE_PERIOD_S

    @property
    def random(self) -> bool:
        return self.noise_mv > 0 or self.period_s > NATIVE_PERIOD_S

    @property
    def seeds(self) -> tuple[int, ...]:
        return SEEDS if self.random else (0,)


CASES = (
    Case("clean", "clean"),
    *(Case(f"noise {s:g} mV", "noise", noise_mv=s) for s in (1, 2, 5, 10)),
    *(Case(f"offset {o:+g} mV", "offset", offset_mv=o) for o in (-5, 5)),
    *(Case(f"LSB {q:g} mV", "lsb", lsb_mv=q) for q in (1, 5)),
    *(Case(f"period {p:g} s", "period", period_s=p) for p in (1, 10, 30, 60)),
    Case("combined", "combined", noise_mv=2, lsb_mv=1, period_s=10),
)


def decimate(t: np.ndarray, period_s: float, phase_s: float) -> np.ndarray:
    """Indices of the native samples a logger ticking every `period_s` would hold.

    Ticks at t[0] + phase + k * period; each keeps the last sample at or before it.
    """
    if period_s <= NATIVE_PERIOD_S:
        return np.arange(len(t))
    ticks = np.arange(t[0] + phase_s, t[-1] + 1e-9, period_s)
    idx = np.searchsorted(t, ticks, side="right") - 1
    return np.unique(idx[idx >= 0])


def quantize(v: np.ndarray, lsb_v: float) -> np.ndarray:
    return np.round(v / lsb_v) * lsb_v if lsb_v > 0 else v


def degrade(t: np.ndarray, v: np.ndarray, case: Case, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    phase = rng.uniform(0.0, case.period_s)  # always drawn, so noise draws line up across cases
    idx = decimate(t, case.period_s, phase)
    t, v = t[idx], v[idx]
    v = v + case.offset_mv / 1000 + (rng.normal(0.0, case.noise_mv / 1000, len(v)) if case.noise_mv > 0 else 0.0)
    return t, quantize(v, case.lsb_mv / 1000)


def trace_rng(seed: int, cell: int, cycle: int) -> np.random.Generator:
    return np.random.default_rng([seed, cell, cycle])


def degraded_features(
    curves: list[Curve], case: Case, seed: int, windows_by_cell: dict[int, set[Win]], detector=detect_window
) -> dict[Win, pd.DataFrame]:
    """Feature tables (same columns as `feature_table`) of the degraded traces, per window."""
    rows: dict[Win, list[dict]] = {}
    for c in curves:
        t, v = degrade(c.t, c.v, case, trace_rng(seed, c.cell, c.cycle))
        for win in windows_by_cell[c.cell]:
            rows.setdefault(win, []).append(feature_row(c, t, v, win, detector))
    return {win: pd.DataFrame(r) for win, r in rows.items()}


def fold_models(
    curves: list[Curve], log: pd.DataFrame, detector=detect_window, calibrate: bool = True
) -> dict[tuple[str, int], tuple[Win, object, float]]:
    """(model, fold) -> (selected window, model fit on the clean training cells, k95).

    k95 is NaN for point models and when `calibrate` is False.
    """
    chosen = log[log.regime == REGIME]
    wins = {Win(r.v1, r.v2) for r in chosen.itertuples()}
    feats = {w: feature_table(curves, w, detector, augment=True) for w in wins}
    cells = sorted({c.cell for c in curves})
    out = {}
    for r in chosen.itertuples():
        win = Win(r.v1, r.v2)
        k = r.k95 if calibrate else np.nan
        out[(r.model, int(r.fold))] = (win, fit_model(feats[win], r.model, [c for c in cells if c != r.fold]), k)
    return out


def run_one(curves: list[Curve], case: Case, seed: int, models: dict, detector: str = MAIN_DETECTOR) -> pd.DataFrame:
    windows_by_cell: dict[int, set[Win]] = {}
    for (_, fold), (win, _, _) in models.items():
        windows_by_cell.setdefault(fold, set()).add(win)
    feats = degraded_features(curves, case, seed, windows_by_cell, DETECTORS[detector])
    out = []
    for (model, fold), (win, est, k) in models.items():
        df = feats[win]
        p = predict_rows(est, df[df.cell == fold], model)
        out.append(p.assign(model=model, v1=win.v1, v2=win.v2, std_cal=p["std"] * k))
    return pd.concat(out, ignore_index=True).assign(case=case.name, seed=seed, detector=detector)


def summarize(preds: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per detector, case and model: metrics pooled over seeds; paired comparisons
    (model vs control) per case for the main detector."""
    rows, pair_rows = [], []
    for det, case in [(d, c) for d in DETECTORS for c in CASES]:
        pc = preds[(preds.case == case.name) & (preds.detector == det)]
        n_seeds = pc.seed.nunique()
        for model in MODELS:
            m = metrics(pc[pc.model == model])
            seed_rmse = pc[pc.model == model].groupby("seed").apply(lambda g: metrics(g)["rmse"], include_groups=False)
            counts = {k: v / n_seeds for k, v in m.items() if k.startswith("n_") and k != "n_total"}
            rows.append(
                dict(
                    detector=det, case=case.name, factor=case.factor, model=model, n_seeds=n_seeds,
                    rmse=m["rmse"], macro_rmse=m["macro_rmse"], mae=m["mae"], max_abs=m["max_abs"],
                    rmse_seed_min=seed_rmse.min(), rmse_seed_max=seed_rmse.max(),
                    answer_rate=m["answer_rate"],
                    coverage95=m.get("coverage95", np.nan), interval_width=m.get("interval_width", np.nan),
                    coverage95_cal=m.get("coverage95_cal", np.nan), interval_width_cal=m.get("interval_width_cal", np.nan),
                    **counts,
                )
            )
        if det != MAIN_DETECTOR:
            continue
        for model, base, adds in PAIRS:
            a, b = pc[pc.model == model], pc[pc.model == base]
            # pooled over seeds: per-cell RMSE over every (seed, trace) both models answered
            summ, _ = paired(a, b, key=("seed", "cell", "cycle"))
            per_seed = [paired(a[a.seed == s], b[b.seed == s])[0]["verdict"] == HELPS for s in sorted(pc.seed.unique())]
            pair_rows.append(
                dict(case=case.name, model=model, base=base, adds=adds, **summ, seeds_helps=int(sum(per_seed)), n_seeds=n_seeds)
            )
    return pd.DataFrame(rows), pd.DataFrame(pair_rows)


def main() -> None:
    curves, _ = load()
    log = pd.read_csv(RESULTS / "window_log.csv")
    t0 = time.perf_counter()
    models = {det: fold_models(curves, log, fn, calibrate=det == MAIN_DETECTOR) for det, fn in DETECTORS.items()}
    tasks = [(det, case, seed) for det in DETECTORS for case in CASES for seed in case.seeds]
    parts = Parallel(n_jobs=-1)(delayed(run_one)(curves, case, seed, models[det], det) for det, case, seed in tasks)
    preds = pd.concat(parts, ignore_index=True)
    print(f"{len(tasks)} degraded runs in {time.perf_counter() - t0:.0f} s")

    summary, pairs = summarize(preds)

    # Consistency gate: the clean case must reproduce the nested any-width result exactly.
    nested_df = pd.read_csv(RESULTS / "clean_nested.csv")
    for col in ("rmse", "coverage95_cal"):
        ref = nested_df[nested_df.regime == REGIME].set_index("model")[col]
        got = summary[(summary.case == "clean") & (summary.detector == MAIN_DETECTOR)].set_index("model")[col]
        if not np.allclose(got[ref.index], ref, atol=1e-4, equal_nan=True):
            raise RuntimeError(f"clean case {col} does not match clean_nested:\n{pd.concat([ref, got], axis=1)}")

    note = (
        "Frozen fold models (each outer fold's model at the window it selected in the any-width "
        "regime, fit on clean training cells) applied to degraded copies of their held-out cell. "
        "Degradation order: sample-and-hold decimation with random phase, offset + Gaussian noise, "
        "rounding to the LSB. Metrics pooled over seeds (20 where noise or phase is random, else 1); "
        "rmse_seed_min/max give the spread of per-seed RMSE; n_<REASON> are mean counts per run. "
        "Errors in SOH percentage points on answered traces. detector `time-below` is the project's "
        "window detector; `first-crossing` is the rule used up to commit 6, kept as a baseline "
        "(fold models refit on its clean features at the same windows). The _cal columns use GPR "
        "intervals calibrated with each fold's k95 from the clean inner fits (main detector only). "
        "Current-sensor error is not "
        "tested: there is no current channel, and a gain error maps one-to-one into dq."
    )
    write_table(summary, "degraded", "Degraded-log tests", note)
    pair_note = (
        "Paired comparison on traces both models answered, pooled over seeds (per-cell RMSE over all "
        f"seeds' traces). Same decision rule as on clean data: the addition (`adds`) helps only if the "
        f"model has lower RMSE than its control in at least {HELPS_MIN_CELLS} of 8 held-out cells. "
        "seeds_helps counts the seeds for which the rule holds on that seed alone."
    )
    write_table(pairs, "degraded_paired", "Degraded-log tests: paired comparison", pair_note)
    plots.degraded(summary)

    cols = ["detector", "case", "model", "rmse", "rmse_seed_min", "rmse_seed_max", "max_abs", "answer_rate", "coverage95", "coverage95_cal"]
    print(summary[cols].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print()
    pcols = ["case", "model", "base", "n_common", "rmse_base", "rmse_model", "cells_model_better", "seeds_helps", "verdict"]
    print(pairs[pcols].to_string(index=False, float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main()
