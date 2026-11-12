"""Degraded-log tests: frozen fold models applied to BMS-like versions of the held-out cell.

Estimators are each outer fold's trained model at the window that fold selected in
the any-width regime (read from `results/window_log.csv`), refit on the clean
training cells and then frozen. Each is applied only to its fold's held-out cell;
the final all-cells model is never used here.

Per trace, in this order:
1. decimate to `period_s` by sample-and-hold on a logger clock with a random phase
   (the last native sample at or before each tick is kept, with its own time stamp);
2. add a constant offset and Gaussian noise;
3. round to the ADC LSB.
Window detection and feature extraction then run on the degraded trace.

Randomness is per trace, from `default_rng([seed, cell, cycle])`, so a result does
not depend on processing order and every case sees the same random numbers for the
same seed. Cases with nothing random run once (seed 0).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from soh import plots
from soh.features import detect_window, ic_features
from soh.load import Curve, load
from soh.models import MODELS, PAIRS
from soh.report import RESULTS, write_table
from soh.validate import IC_HELPS_MIN_CELLS, Win, feature_table, fit_model, metrics, paired, predict_rows

NATIVE_PERIOD_S = 1.0
SEEDS = tuple(range(20))
REGIME = "any"


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


def degraded_features(curves: list[Curve], case: Case, seed: int, windows_by_cell: dict[int, set[Win]]) -> dict[Win, pd.DataFrame]:
    """Feature tables (same columns as `feature_table`) of the degraded traces, per window."""
    rows: dict[Win, list[dict]] = {}
    for c in curves:
        t, v = degrade(c.t, c.v, case, trace_rng(seed, c.cell, c.cycle))
        for win in windows_by_cell[c.cell]:
            w = detect_window(t, v, win.v1, win.v2)
            ic = ic_features(t, v, w, win.v1, win.v2)
            rows.setdefault(win, []).append(
                dict(
                    cell=c.cell, cycle=c.cycle, reason=w.reason.value, ic_reason=ic.reason.value,
                    dq=w.dq, ic_peak_h=ic.peak_h, ic_peak_v=ic.peak_v, duration_s=w.duration_s,
                    capacity=c.capacity_mah, c0=c.c0_mah,
                )
            )
    return {win: pd.DataFrame(r) for win, r in rows.items()}


def fold_models(curves: list[Curve], log: pd.DataFrame) -> dict[tuple[str, int], tuple[Win, object]]:
    """(model, fold) -> (selected window, model fit on the clean training cells)."""
    chosen = log[log.regime == REGIME]
    wins = {Win(r.v1, r.v2) for r in chosen.itertuples()}
    feats = {w: feature_table(curves, w) for w in wins}
    cells = sorted({c.cell for c in curves})
    out = {}
    for r in chosen.itertuples():
        win = Win(r.v1, r.v2)
        out[(r.model, int(r.fold))] = (win, fit_model(feats[win], r.model, [c for c in cells if c != r.fold]))
    return out


def run_one(curves: list[Curve], case: Case, seed: int, models: dict) -> pd.DataFrame:
    windows_by_cell: dict[int, set[Win]] = {}
    for (_, fold), (win, _) in models.items():
        windows_by_cell.setdefault(fold, set()).add(win)
    feats = degraded_features(curves, case, seed, windows_by_cell)
    out = []
    for (model, fold), (win, est) in models.items():
        df = feats[win]
        out.append(predict_rows(est, df[df.cell == fold], model).assign(model=model, v1=win.v1, v2=win.v2))
    return pd.concat(out, ignore_index=True).assign(case=case.name, seed=seed)


def summarize(preds: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per case and model: metrics pooled over seeds; paired IC comparisons per case."""
    rows, pair_rows = [], []
    for case in CASES:
        pc = preds[preds.case == case.name]
        n_seeds = pc.seed.nunique()
        for model in MODELS:
            m = metrics(pc[pc.model == model])
            seed_rmse = pc[pc.model == model].groupby("seed").apply(lambda g: metrics(g)["rmse"], include_groups=False)
            counts = {k: v / n_seeds for k, v in m.items() if k.startswith("n_") and k != "n_total"}
            rows.append(
                dict(
                    case=case.name, factor=case.factor, model=model, n_seeds=n_seeds,
                    rmse=m["rmse"], macro_rmse=m["macro_rmse"], mae=m["mae"], max_abs=m["max_abs"],
                    rmse_seed_min=seed_rmse.min(), rmse_seed_max=seed_rmse.max(),
                    answer_rate=m["answer_rate"],
                    coverage95=m.get("coverage95", np.nan), interval_width=m.get("interval_width", np.nan),
                    **counts,
                )
            )
        for ic_model, base in PAIRS:
            a, b = pc[pc.model == ic_model], pc[pc.model == base]
            # pooled over seeds: per-cell RMSE over every (seed, trace) both models answered
            summ, _ = paired(a, b, key=("seed", "cell", "cycle"))
            per_seed = [
                paired(a[a.seed == s], b[b.seed == s])[0]["verdict"] == "IC helps" for s in sorted(pc.seed.unique())
            ]
            pair_rows.append(
                dict(case=case.name, ic_model=ic_model, base_model=base, **summ, seeds_ic_helps=int(sum(per_seed)), n_seeds=n_seeds)
            )
    return pd.DataFrame(rows), pd.DataFrame(pair_rows)


def main() -> None:
    curves, _ = load()
    log = pd.read_csv(RESULTS / "window_log.csv")
    t0 = time.perf_counter()
    models = fold_models(curves, log)
    tasks = [(case, seed) for case in CASES for seed in case.seeds]
    parts = Parallel(n_jobs=-1)(delayed(run_one)(curves, case, seed, models) for case, seed in tasks)
    preds = pd.concat(parts, ignore_index=True)
    print(f"{len(tasks)} degraded runs in {time.perf_counter() - t0:.0f} s")

    summary, pairs = summarize(preds)

    # Consistency gate: the clean case must reproduce the nested any-width result exactly.
    nested_df = pd.read_csv(RESULTS / "clean_nested.csv")
    ref = nested_df[nested_df.regime == REGIME].set_index("model").rmse
    got = summary[summary.case == "clean"].set_index("model").rmse
    if not np.allclose(got[ref.index], ref, atol=1e-4, equal_nan=True):
        raise RuntimeError(f"clean case does not match clean_nested:\n{pd.concat([ref, got], axis=1)}")

    note = (
        "Frozen fold models (each outer fold's model at the window it selected in the any-width "
        "regime, fit on clean training cells) applied to degraded copies of their held-out cell. "
        "Degradation order: sample-and-hold decimation with random phase, offset + Gaussian noise, "
        "rounding to the LSB. Metrics pooled over seeds (20 where noise or phase is random, else 1); "
        "rmse_seed_min/max give the spread of per-seed RMSE; n_<REASON> are mean counts per run. "
        "Errors in SOH percentage points on answered traces. Current-sensor error is not tested: "
        "there is no current channel, and a gain error maps one-to-one into dq."
    )
    write_table(summary, "degraded", "Degraded-log tests", note)
    pair_note = (
        "Paired comparison on traces both models answered, pooled over seeds (per-cell RMSE over all "
        f"seeds' traces). Same decision rule as on clean data: IC helps only if the IC model has lower "
        f"RMSE in at least {IC_HELPS_MIN_CELLS} of 8 held-out cells. seeds_ic_helps counts the seeds for "
        "which the rule holds on that seed alone."
    )
    write_table(pairs, "degraded_paired_ic", "Degraded-log tests: paired IC comparison", pair_note)
    plots.degraded(summary)

    cols = ["case", "model", "rmse", "rmse_seed_min", "rmse_seed_max", "max_abs", "answer_rate", "coverage95"]
    print(summary[cols].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print()
    pcols = ["case", "ic_model", "base_model", "n_common", "rmse_base", "rmse_ic", "cells_ic_better", "seeds_ic_helps", "verdict"]
    print(pairs[pcols].to_string(index=False, float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main()
