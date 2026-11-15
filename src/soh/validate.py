"""Nested leave-one-cell-out validation with window selection.

Outer loop: leave one cell out (8 folds). Inside each fold, every model picks its
own window from a fixed grid by inner leave-one-cell-out on the 7 training cells:

- score = mean over inner held-out cells of that cell's RMSE (SOH points);
- eligible only if the model answers >= MIN_ANSWER_RATE of inner held-out traces;
- ties go to the narrower window, then the lower V1;
- no eligible window -> SelectionError. Decided with the author for IC models at
  100 mV: that regime is reported as "no eligible window" with the best window's
  answer rate; the rule itself is not relaxed.

The held-out cell is never used for any choice.

GPR intervals are also reported calibrated: in each outer fold, k = 95th percentile
of |error| / std over the inner held-out predictions at the fold's chosen window
(the inner fits above, on the 7 training cells only), divided by 1.96. The held-out
cell's std is multiplied by k (`std_cal`). k may be below 1 (narrower intervals). Width-frontier regimes repeat the
selection with the grid restricted to one width, reusing the cached inner scores.

A model answers a trace only when its features exist (reason OK). Training uses
answered training traces; error metrics use answered held-out traces; every
unanswered trace is counted by reason.

M6 also trains on AUG_COPIES copies of each training trace shifted by a constant
offset ~ U(-AUG_MAX_MV, +AUG_MAX_MV) mV. Copies are never predicted or scored.

Fits are shared where the training set is identical: the inner fit that leaves out
{fold F, inner cell H} serves fold F (predicting H) and fold H (predicting F), and
each outer fit (all cells but F) is made once and reused across regimes. GPR fits
run in parallel; each is deterministic (fixed seed), so the order does not matter.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from itertools import combinations
from math import comb

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from soh.features import END_BAND_V, NO_ESTIMATE_REASONS, Reason, detect_window, ic_features
from soh.load import Curve, load
from soh.models import MODELS, PAIRS
from soh import plots
from soh.report import write_table

V1_GRID = (3.5, 3.6, 3.7, 3.8, 3.9)
WIDTHS_MV = (100, 200, 300, 400)
CUTOFF_MARGIN_V = 0.050
MIN_ANSWER_RATE = 0.95
REGIMES = ("any",) + tuple(f"w{w}" for w in WIDTHS_MV)
HELPS_MIN_CELLS = 7  # decision rule: model better than its control in >= 7 of 8 held-out cells
HELPS = "helps"
Z95 = 1.959964  # two-sided 95 % normal quantile
CAL_QUANTILE = 0.95
AUG_COPIES = 2
AUG_MAX_MV = 8.0
AUG_SEED = 1000


class SelectionError(RuntimeError):
    """No window is eligible for a fold."""


@dataclass(frozen=True, order=True)
class Win:
    v1: float
    v2: float

    @property
    def width_mv(self) -> int:
        return round(1000 * (self.v2 - self.v1))

    def __str__(self) -> str:
        return f"{self.v1:.1f}-{self.v2:.1f}"


def window_grid(cutoff_v: float) -> list[Win]:
    """V1 x width grid, keeping only V2 <= cutoff - 50 mV."""
    assert END_BAND_V < CUTOFF_MARGIN_V, "detector end band must fit below the charge cutoff"
    v2_max = cutoff_v - CUTOFF_MARGIN_V + 1e-9
    return [
        Win(v1, round(v1 + w / 1000, 3)) for v1 in V1_GRID for w in WIDTHS_MV if v1 + w / 1000 <= v2_max
    ]


def feature_row(c: Curve, t: np.ndarray, v: np.ndarray, win: Win, detector=detect_window) -> dict:
    """Features of one trace (t, v) of curve `c` at window `win`."""
    w = detector(t, v, win.v1, win.v2)
    ic = ic_features(t, v, w, win.v1, win.v2)
    return dict(
        cell=c.cell,
        cycle=c.cycle,
        reason=w.reason.value,
        ic_reason=ic.reason.value,
        dq=w.dq,
        dq_a=w.dq_a,
        dq_b=w.dq_b,
        ic_peak_h=ic.peak_h,
        ic_peak_v=ic.peak_v,
        duration_s=w.duration_s,
        capacity=c.capacity_mah,
        c0=c.c0_mah,
    )


def aug_offsets_mv(c: Curve) -> np.ndarray:
    """Offsets [mV] of one trace's augmented copies."""
    return np.random.default_rng([AUG_SEED, c.cell, c.cycle]).uniform(-AUG_MAX_MV, AUG_MAX_MV, AUG_COPIES)


def feature_table(curves: list[Curve], win: Win, detector=detect_window, augment: bool = False) -> pd.DataFrame:
    """Features of every trace (`aug` = 0); with `augment`, also of its offset copies (`aug` > 0)."""
    rows = [{**feature_row(c, c.t, c.v, win, detector), "aug": 0} for c in curves]
    if augment:
        for c in curves:
            for k, o in enumerate(aug_offsets_mv(c), start=1):
                rows.append({**feature_row(c, c.t, c.v + o / 1000, win, detector), "aug": k})
    return pd.DataFrame(rows)


def originals(df: pd.DataFrame) -> pd.DataFrame:
    """The measured traces of a feature table, without augmented copies."""
    return df[df.aug == 0] if "aug" in df else df


def model_reason(df: pd.DataFrame, model: str) -> pd.Series:
    """The model's own reason per row: IC models need the IC reason too (no fallback)."""
    return df.ic_reason if MODELS[model].needs_ic else df.reason


def _X(d: pd.DataFrame, model: str) -> np.ndarray:
    cols = list(MODELS[model].cols)
    return d[cols].to_numpy() if cols else np.zeros((len(d), 1))


def fit_model(df: pd.DataFrame, model: str, train_cells):
    """Fit on the answered rows of `train_cells`; None if there are none."""
    if not MODELS[model].augment:
        df = originals(df)
    train = df[df.cell.isin(train_cells) & (model_reason(df, model) == Reason.OK.value)]
    if train.empty:
        return None
    return MODELS[model].factory().fit(_X(train, model), train.capacity.to_numpy())


def predict_rows(est, test: pd.DataFrame, model: str) -> pd.DataFrame:
    """`test` rows with `pred`, `std` [mAh] and the model's `reason`; NaN where no estimate."""
    test = test.assign(reason=model_reason(test, model), pred=np.nan, std=np.nan)
    ok = test.reason == Reason.OK.value
    if est is None:
        test.loc[ok, "reason"] = Reason.NO_TRAIN.value
    elif ok.any():
        if MODELS[model].has_std:
            mu, sd = est.predict(_X(test[ok], model), return_std=True)
            test.loc[ok, "pred"], test.loc[ok, "std"] = mu, sd
        else:
            test.loc[ok, "pred"] = est.predict(_X(test[ok], model))
    return test


def fit_predict(df: pd.DataFrame, model: str, test_cells, train_cells) -> pd.DataFrame:
    """Fit `model` on the answered rows of `train_cells`, predict the rows of `test_cells`."""
    test = originals(df)
    return predict_rows(fit_model(df, model, train_cells), test[test.cell.isin(test_cells)], model)


def loco(df: pd.DataFrame, model: str, cells: list[int] | None = None) -> pd.DataFrame:
    """Leave-one-cell-out over `cells` (default: all cells in `df`).

    Each cell in `cells` is predicted by a model fit on the other cells in `cells`.
    Rows of other cells are ignored.
    """
    cells = sorted(df.cell.unique()) if cells is None else sorted(cells)
    parts = [fit_predict(df, model, [h], [c for c in cells if c != h]) for h in cells]
    return pd.concat(parts, ignore_index=True)


def n_jobs(model: str) -> int:
    return -1 if MODELS[model].has_std else 1


def metrics(pred: pd.DataFrame) -> dict[str, float]:
    """Errors in SOH percentage points, 100 * (pred - capacity) / c0, on answered traces."""
    n_total = len(pred)
    ans = pred[pred.pred.notna()]
    err = 100.0 * (ans.pred - ans.capacity) / ans.c0
    if len(err):
        per_cell_rmse = err.groupby(ans.cell).apply(lambda e: np.sqrt(np.mean(e**2)))
        stats = dict(
            rmse=float(np.sqrt(np.mean(err**2))),
            macro_rmse=float(per_cell_rmse.mean()),
            mae=float(np.mean(np.abs(err))),
            max_abs=float(np.max(np.abs(err))),
        )
    else:
        stats = dict(rmse=np.nan, macro_rmse=np.nan, mae=np.nan, max_abs=np.nan)
    for sfx in ("", "_cal"):  # raw and calibrated GPR intervals
        if f"std{sfx}" in ans and ans[f"std{sfx}"].notna().any():
            half = Z95 * ans[f"std{sfx}"]
            stats[f"coverage95{sfx}"] = float(np.mean(np.abs(ans.pred - ans.capacity) <= half))
            stats[f"interval_width{sfx}"] = float(np.mean(100.0 * 2 * half / ans.c0))  # SOH points
    counts = {f"n_{r.value}": int((pred.reason == r.value).sum()) for r in NO_ESTIMATE_REASONS}
    return dict(**stats, n=len(err), n_total=n_total, answer_rate=len(err) / n_total, **counts)


def calibration_factor(pred: pd.DataFrame) -> float:
    """k such that k * std covers CAL_QUANTILE of these answered predictions' errors at
    +-Z95 * k * std: quantile(|error| / std) / Z95. NaN without answered GPR predictions."""
    ans = pred[pred.pred.notna() & pred["std"].notna()]
    if ans.empty:
        return float("nan")
    z = np.abs(ans.pred - ans.capacity) / ans["std"]
    return float(np.quantile(z, CAL_QUANTILE) / Z95)


def inner_scores(features: dict[Win, pd.DataFrame], model: str) -> pd.DataFrame:
    """Inner leave-one-cell-out score of every (outer fold, window). Held-out cell excluded.

    One fit per (window, cell pair {a, b}) on the other six cells; it predicts a for
    fold b and b for fold a. GPR models also get the fold's calibration factor `k95`.
    """
    tasks = []
    for win, df in features.items():
        cells = sorted(df.cell.unique())
        for a, b in combinations(cells, 2):
            tasks.append((win, a, b, [c for c in cells if c not in (a, b)]))
    fits = Parallel(n_jobs=n_jobs(model))(
        delayed(fit_predict)(features[win], model, [a, b], train) for win, a, b, train in tasks
    )
    by_pair = {(win, a, b): f for (win, a, b, _), f in zip(tasks, fits)}
    rows = []
    for win, df in features.items():
        cells = sorted(df.cell.unique())
        for held in cells:
            parts = [by_pair[(win, min(held, h), max(held, h))] for h in cells if h != held]
            pred = pd.concat([p[p.cell != held] for p in parts], ignore_index=True)
            m = metrics(pred)
            rows.append(
                dict(
                    model=model,
                    fold=held,
                    v1=win.v1,
                    v2=win.v2,
                    width_mv=win.width_mv,
                    score=m["macro_rmse"],
                    answer_rate=m["answer_rate"],
                    k95=calibration_factor(pred) if MODELS[model].has_std else np.nan,
                )
            )
    return pd.DataFrame(rows)


def select(scores: pd.DataFrame, regime: str) -> pd.DataFrame:
    """Pick one window per fold from cached inner scores. One row per fold."""
    s = scores if regime == "any" else scores[scores.width_mv == int(regime[1:])]
    rows = []
    for fold, g in s.groupby("fold"):
        eligible = g[(g.answer_rate >= MIN_ANSWER_RATE) & g.score.notna()]
        if eligible.empty:
            raise SelectionError(f"fold {fold}, regime {regime}: no window answers >= {MIN_ANSWER_RATE:.0%}")
        best = eligible.sort_values(["score", "width_mv", "v1"], kind="mergesort").iloc[0]
        rows.append(
            dict(
                fold=int(fold),
                v1=best.v1,
                v2=best.v2,
                width_mv=int(best.width_mv),
                inner_score=best.score,
                inner_answer_rate=best.answer_rate,
                k95=best.get("k95", np.nan),
                n_eligible=len(eligible),
                n_candidates=len(g),
            )
        )
    return pd.DataFrame(rows)


def outer_fits(features: dict[Win, pd.DataFrame], model: str, keys) -> dict:
    """Held-out predictions for each (window, fold) in `keys`, fit on the other cells."""
    keys = sorted(set(keys))

    def one(win, fold):
        df = features[win]
        return fit_predict(df, model, [fold], [c for c in df.cell.unique() if c != fold])

    fits = Parallel(n_jobs=n_jobs(model))(delayed(one)(w, f) for w, f in keys)
    return dict(zip(keys, fits))


def outer_predict(fits: dict, chosen: pd.DataFrame) -> pd.DataFrame:
    """Each held-out cell predicted at its fold's chosen window, std calibrated by its k95."""
    out = [
        (f := fits[(Win(r.v1, r.v2), r.fold)]).assign(v1=r.v1, v2=r.v2, std_cal=f["std"] * r.k95)
        for r in chosen.itertuples()
    ]
    return pd.concat(out, ignore_index=True)


def nested(features: dict[Win, pd.DataFrame], model: str, regimes=REGIMES):
    """Return (pooled rows, per-cell rows, window log rows, inner scores, predictions by regime)."""
    scores = inner_scores(features, model)
    picks = {}
    for regime in regimes:
        try:
            picks[regime] = select(scores, regime)
        except SelectionError:
            picks[regime] = None
    keys = [(Win(r.v1, r.v2), r.fold) for c in picks.values() if c is not None for r in c.itertuples()]
    fits = outer_fits(features, model, keys)
    pooled, cells, log, preds = [], [], [], {}
    for regime, chosen in picks.items():
        if chosen is None:
            pooled.append(dict(model=model, regime=regime, n=0, answer_rate=0.0, windows=not_available(scores, regime)))
            preds[regime] = None
            continue
        pred = outer_predict(fits, chosen)
        answered = pred.pred.notna()
        counts = chosen.apply(lambda r: f"{r.v1:.1f}-{r.v2:.1f}", axis=1).value_counts()
        windows = "; ".join(f"{w} x{n}" for w, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
        pooled.append(
            dict(
                model=model,
                regime=regime,
                **metrics(pred),
                median_window_s=float(pred.duration_s[answered].median()),
                windows=windows,
            )
        )
        for cell, g in pred.groupby("cell"):
            m = metrics(g)
            del m["macro_rmse"]  # equals rmse for a single cell
            cells.append(
                dict(
                    model=model,
                    regime=regime,
                    cell=int(cell),
                    window=f"{g.v1.iloc[0]:.1f}-{g.v2.iloc[0]:.1f}",
                    **m,
                    median_window_s=float(g.duration_s[g.pred.notna()].median()),
                )
            )
        log.append(chosen.assign(model=model, regime=regime))
        preds[regime] = pred
    return pooled, cells, log, scores, preds


def not_available(scores: pd.DataFrame, regime: str) -> str:
    """Describe a regime with no eligible window: best window by mean inner answer rate."""
    s = scores if regime == "any" else scores[scores.width_mv == int(regime[1:])]
    rate = s.groupby(["v1", "v2"]).answer_rate.mean()
    (v1, v2), best = rate.idxmax(), rate.max()
    return f"no eligible window (best {v1:.1f}-{v2:.1f} V answers {100 * best:.0f} %)"


def sign_test_p(k: int, n: int) -> float:
    """One-sided P(X >= k) for X ~ Binomial(n, 1/2)."""
    return sum(comb(n, j) for j in range(k, n + 1)) / 2**n


def paired(pred_model: pd.DataFrame, pred_base: pd.DataFrame, key=("cell", "cycle")) -> tuple[dict, pd.DataFrame]:
    """Compare a model with its control on the traces both answered (each at its own
    selected window).

    `key` identifies a trace; it must include `cell` (the decision rule counts cells).
    """
    key = list(key)
    a = pred_model[key + ["pred", "capacity", "c0"]].rename(columns={"pred": "pred_model"})
    b = pred_base[key + ["pred"]].rename(columns={"pred": "pred_base"})
    m = a.merge(b, on=key).dropna(subset=["pred_model", "pred_base"])
    if m.empty:
        return dict(n_common=0, verdict="n/a (no commonly answered traces)"), pd.DataFrame()
    for side in ("model", "base"):
        m[f"err_{side}"] = 100.0 * (m[f"pred_{side}"] - m.capacity) / m.c0
    rmse = lambda e: float(np.sqrt(np.mean(e**2)))  # noqa: E731
    per_cell = (
        m.groupby("cell")
        .apply(lambda g: pd.Series(dict(n=len(g), rmse_base=rmse(g.err_base), rmse_model=rmse(g.err_model))), include_groups=False)
        .reset_index()
    )
    per_cell["model_better"] = per_cell.rmse_model < per_cell.rmse_base
    k, n = int(per_cell.model_better.sum()), len(per_cell)
    summary = dict(
        n_common=len(m),
        rmse_base=rmse(m.err_base),
        rmse_model=rmse(m.err_model),
        macro_rmse_base=float(per_cell.rmse_base.mean()),
        macro_rmse_model=float(per_cell.rmse_model.mean()),
        cells_model_better=k,
        n_cells=n,
        sign_test_p=sign_test_p(k, n),
        verdict=HELPS if n == 8 and k >= HELPS_MIN_CELLS else "no detectable gain",
    )
    return summary, per_cell


def main() -> None:
    curves, audit = load()
    grid = window_grid(round(audit.cutoff_v[0], 2))
    features = {w: feature_table(curves, w, augment=True) for w in grid}
    print(f"{len(grid)} windows: {', '.join(map(str, grid))}")

    pooled, cells, log, scores, preds = [], [], [], [], {}
    for name in MODELS:
        t0 = time.perf_counter()
        p, c, lg, s, pr = nested(features, name)
        print(f"{name}: {time.perf_counter() - t0:.0f} s", flush=True)
        pooled += p
        cells += c
        log += lg
        scores.append(s)
        preds[name] = pr

    pair_rows, pair_cells = [], []
    for model, base, adds in PAIRS:
        for regime in REGIMES:
            tag = dict(model=model, base=base, adds=adds, regime=regime)
            if preds[model][regime] is None or preds[base][regime] is None:
                pair_rows.append({**tag, "verdict": "n/a (no eligible window)"})
                continue
            summ, pc = paired(preds[model][regime], preds[base][regime])
            pair_rows.append({**tag, **summ})
            pair_cells.append(pc.assign(**tag))

    note = (
        "Nested leave-one-cell-out: each model picks its window inside each outer fold by inner "
        "leave-one-cell-out on the 7 training cells. Regime `any` searches the full grid; `wNNN` "
        "restricts it to one width (mV). Errors in SOH percentage points on answered traces; "
        "n_<REASON> counts traces with no estimate. IC settings were frozen before the first run with "
        "M2. For windows starting at 3.8 V, early-life traces (first 600-800 cycles) give IC_EDGE "
        "partly because of a smoothing edge artifact: their dQ/dV peak (~3.82 V) lies within the "
        "Savitzky-Golay half-width of V1, and edge extrapolation puts the maximum in the first bin. "
        "M5 is GPR on the window's two halves, dq_a (V1 to the midpoint) and dq_b (midpoint to V2). "
        f"M6 is M5 trained also on {AUG_COPIES} copies of each training trace shifted by a constant "
        f"offset drawn from U(-{AUG_MAX_MV:g}, +{AUG_MAX_MV:g}) mV; it is scored and selects its window "
        "on measured traces only. "
        "GPR models (M3, M4, M5): coverage95 is the share of answered traces whose measured capacity lies "
        "inside the 95 % predictive interval; interval_width is its mean full width in SOH points. "
        "The _cal columns use the std multiplied by the fold's k95 (95th percentile of |error| / std "
        "over the inner held-out predictions at the chosen window, training cells only, / 1.96)."
    )
    pooled_df = pd.DataFrame(pooled)
    write_table(pooled_df, "clean_nested", "Clean data, nested validation", note)
    cells_df = pd.DataFrame(cells)
    write_table(cells_df, "clean_nested_per_cell", "Clean data, nested validation, per cell", note)
    plots.frontier(pooled_df, cells_df)
    log_df = pd.concat(log, ignore_index=True)
    log_cols = ["model", "regime", "fold", "v1", "v2", "width_mv", "inner_score", "inner_answer_rate", "k95", "n_eligible", "n_candidates"]
    write_table(log_df[log_cols], "window_log", "Selected window per outer fold", note)
    write_table(pd.concat(scores, ignore_index=True), "inner_scores", "Inner leave-one-cell-out scores", note)
    pair_note = (
        "Each model is compared with its control (`adds` names what the model adds) on the held-out "
        "traces both answered, each model at its own selected window. Decision rule fixed in advance: "
        f"the addition helps only if the model has lower RMSE than its control in at least "
        f"{HELPS_MIN_CELLS} of 8 held-out cells (one-sided sign test). In regime "
        "`any` the two models may use different windows, so a gain there can come partly from a longer "
        "window; the `wNNN` rows compare at equal width."
    )
    pair_df = pd.DataFrame(pair_rows)
    write_table(pair_df, "paired", "Paired comparison: model vs control", pair_note)
    pc_cols = ["model", "base", "adds", "regime", "cell", "n", "rmse_base", "rmse_model", "model_better"]
    write_table(pd.concat(pair_cells, ignore_index=True)[pc_cols], "paired_per_cell", "Paired comparison per cell", pair_note)

    common = log_df[(log_df.regime == "any")].groupby("model").apply(
        lambda g: g.groupby(["v1", "v2"]).size().idxmax(), include_groups=False
    )
    plots.charge_curves(curves, {m: Win(*common[m]) for m in ("M1", "M2")})
    plots.predictions({m: preds[m]["any"] for m in ("M3", "M4")})

    cols = ["model", "regime", "rmse", "macro_rmse", "mae", "max_abs", "answer_rate", "coverage95",
            "interval_width", "coverage95_cal", "interval_width_cal", "median_window_s", "windows"]
    print(pooled_df[cols].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print()
    print(pair_df.to_string(index=False, float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main()
