"""Nested leave-one-cell-out validation with window selection.

Outer loop: leave one cell out (8 folds). Inside each fold, every model picks its
own window from a fixed grid by inner leave-one-cell-out on the 7 training cells:

- score = mean over inner held-out cells of that cell's RMSE (SOH points);
- eligible only if the model answers >= MIN_ANSWER_RATE of inner held-out traces;
- ties go to the narrower window, then the lower V1;
- no eligible window -> SelectionError. Decided with the author for IC models at
  100 mV: that regime is reported as "no eligible window" with the best window's
  answer rate; the rule itself is not relaxed.

The held-out cell is never used for any choice. Width-frontier regimes repeat the
selection with the grid restricted to one width, reusing the cached inner scores.

A model answers a trace only when its features exist (reason OK). Training uses
answered training traces; error metrics use answered held-out traces; every
unanswered trace is counted by reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import comb

import numpy as np
import pandas as pd

from soh.features import NO_ESTIMATE_REASONS, Reason, detect_window, ic_features
from soh.load import Curve, load
from soh.models import MODELS, PAIRS
from soh import plots
from soh.report import write_table

V1_GRID = (3.5, 3.6, 3.7, 3.8, 3.9)
WIDTHS_MV = (100, 200, 300, 400)
CUTOFF_MARGIN_V = 0.050
MIN_ANSWER_RATE = 0.95
REGIMES = ("any",) + tuple(f"w{w}" for w in WIDTHS_MV)
IC_HELPS_MIN_CELLS = 7  # decision rule: IC model better in >= 7 of 8 held-out cells


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
    v2_max = cutoff_v - CUTOFF_MARGIN_V + 1e-9
    return [
        Win(v1, round(v1 + w / 1000, 3)) for v1 in V1_GRID for w in WIDTHS_MV if v1 + w / 1000 <= v2_max
    ]


def feature_table(curves: list[Curve], win: Win) -> pd.DataFrame:
    rows = []
    for c in curves:
        w = detect_window(c.t, c.v, win.v1, win.v2)
        ic = ic_features(c.t, c.v, w, win.v1, win.v2)
        rows.append(
            dict(
                cell=c.cell,
                cycle=c.cycle,
                reason=w.reason.value,
                ic_reason=ic.reason.value,
                dq=w.dq,
                ic_peak_h=ic.peak_h,
                ic_peak_v=ic.peak_v,
                duration_s=w.duration_s,
                capacity=c.capacity_mah,
                c0=c.c0_mah,
            )
        )
    return pd.DataFrame(rows)


def loco(df: pd.DataFrame, model: str, cells: list[int] | None = None) -> pd.DataFrame:
    """Leave-one-cell-out over `cells` (default: all cells in `df`).

    Each cell in `cells` is predicted by a model fit on the other cells in `cells`.
    Rows of other cells are ignored. Returns the predicted rows with `pred` in mAh
    (NaN where the model gives no estimate) and `reason` set to the model's own
    reason: for IC models a missing IC peak is a no-estimate, with no fallback.
    """
    spec = MODELS[model]
    cells = sorted(df.cell.unique()) if cells is None else sorted(cells)
    df = df[df.cell.isin(cells)].copy()
    if spec.needs_ic:
        df["reason"] = df.ic_reason
    answered = df.reason == Reason.OK.value
    cols = list(spec.cols)
    X = lambda d: d[cols].to_numpy() if cols else np.zeros((len(d), 1))  # noqa: E731
    out = []
    for held in cells:
        train = df[(df.cell != held) & answered]
        test = df[df.cell == held].copy()
        test["pred"] = np.nan
        ok = test.reason == Reason.OK.value
        if train.empty:
            test.loc[ok, "reason"] = Reason.NO_TRAIN.value
        elif ok.any():
            m = spec.factory().fit(X(train), train.capacity.to_numpy())
            test.loc[ok, "pred"] = m.predict(X(test[ok]))
        out.append(test)
    return pd.concat(out, ignore_index=True)


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
    counts = {f"n_{r.value}": int((pred.reason == r.value).sum()) for r in NO_ESTIMATE_REASONS}
    return dict(**stats, n=len(err), n_total=n_total, answer_rate=len(err) / n_total, **counts)


def inner_scores(features: dict[Win, pd.DataFrame], model: str) -> pd.DataFrame:
    """Inner leave-one-cell-out score of every (outer fold, window). Held-out cell excluded."""
    rows = []
    for win, df in features.items():
        cells = sorted(df.cell.unique())
        for held in cells:
            pred = loco(df, model, [c for c in cells if c != held])
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
                n_eligible=len(eligible),
                n_candidates=len(g),
            )
        )
    return pd.DataFrame(rows)


def outer_predict(features: dict[Win, pd.DataFrame], model: str, chosen: pd.DataFrame) -> pd.DataFrame:
    """Predict each held-out cell at its fold's chosen window, fit on the other 7 cells."""
    out = []
    for r in chosen.itertuples():
        df = features[Win(r.v1, r.v2)]
        pred = loco(df, model)
        out.append(pred[pred.cell == r.fold].assign(v1=r.v1, v2=r.v2))
    return pd.concat(out, ignore_index=True)


def nested(features: dict[Win, pd.DataFrame], model: str, regimes=REGIMES):
    """Return (pooled rows, per-cell rows, window log rows, inner scores, predictions by regime)."""
    scores = inner_scores(features, model)
    pooled, cells, log, preds = [], [], [], {}
    for regime in regimes:
        try:
            chosen = select(scores, regime)
        except SelectionError:
            pooled.append(dict(model=model, regime=regime, n=0, answer_rate=0.0, windows=not_available(scores, regime)))
            preds[regime] = None
            continue
        pred = outer_predict(features, model, chosen)
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


def paired(pred_ic: pd.DataFrame, pred_base: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """Compare two models on the traces both answered (each at its own selected window)."""
    key = ["cell", "cycle"]
    a = pred_ic[key + ["pred", "capacity", "c0"]].rename(columns={"pred": "pred_ic"})
    b = pred_base[key + ["pred"]].rename(columns={"pred": "pred_base"})
    m = a.merge(b, on=key).dropna(subset=["pred_ic", "pred_base"])
    for side in ("ic", "base"):
        m[f"err_{side}"] = 100.0 * (m[f"pred_{side}"] - m.capacity) / m.c0
    rmse = lambda e: float(np.sqrt(np.mean(e**2)))  # noqa: E731
    per_cell = (
        m.groupby("cell")
        .apply(lambda g: pd.Series(dict(n=len(g), rmse_base=rmse(g.err_base), rmse_ic=rmse(g.err_ic))), include_groups=False)
        .reset_index()
    )
    per_cell["ic_better"] = per_cell.rmse_ic < per_cell.rmse_base
    k, n = int(per_cell.ic_better.sum()), len(per_cell)
    summary = dict(
        n_common=len(m),
        rmse_base=rmse(m.err_base),
        rmse_ic=rmse(m.err_ic),
        macro_rmse_base=float(per_cell.rmse_base.mean()),
        macro_rmse_ic=float(per_cell.rmse_ic.mean()),
        cells_ic_better=k,
        n_cells=n,
        sign_test_p=sign_test_p(k, n),
        verdict="IC helps" if n == 8 and k >= IC_HELPS_MIN_CELLS else "no detectable gain",
    )
    return summary, per_cell


def main() -> None:
    curves, audit = load()
    grid = window_grid(round(audit.cutoff_v[0], 2))
    features = {w: feature_table(curves, w) for w in grid}
    print(f"{len(grid)} windows: {', '.join(map(str, grid))}")

    pooled, cells, log, scores, preds = [], [], [], [], {}
    for name in MODELS:
        p, c, lg, s, pr = nested(features, name)
        pooled += p
        cells += c
        log += lg
        scores.append(s)
        preds[name] = pr

    pair_rows, pair_cells = [], []
    for ic_model, base in PAIRS:
        for regime in REGIMES:
            tag = dict(ic_model=ic_model, base_model=base, regime=regime)
            if preds[ic_model][regime] is None or preds[base][regime] is None:
                pair_rows.append({**tag, "verdict": "n/a (no eligible window)"})
                continue
            summ, pc = paired(preds[ic_model][regime], preds[base][regime])
            pair_rows.append({**tag, **summ})
            pair_cells.append(pc.assign(**tag))

    note = (
        "Nested leave-one-cell-out: each model picks its window inside each outer fold by inner "
        "leave-one-cell-out on the 7 training cells. Regime `any` searches the full grid; `wNNN` "
        "restricts it to one width (mV). Errors in SOH percentage points on answered traces; "
        "n_<REASON> counts traces with no estimate. IC settings were frozen before the first run with "
        "M2. For windows starting at 3.8 V, early-life traces (first 600-800 cycles) give IC_EDGE "
        "partly because of a smoothing edge artifact: their dQ/dV peak (~3.82 V) lies within the "
        "Savitzky-Golay half-width of V1, and edge extrapolation puts the maximum in the first bin."
    )
    pooled_df = pd.DataFrame(pooled)
    write_table(pooled_df, "clean_nested", "Clean data, nested validation", note)
    cells_df = pd.DataFrame(cells)
    write_table(cells_df, "clean_nested_per_cell", "Clean data, nested validation, per cell", note)
    plots.frontier(pooled_df, cells_df)
    log_df = pd.concat(log, ignore_index=True)
    log_cols = ["model", "regime", "fold", "v1", "v2", "width_mv", "inner_score", "inner_answer_rate", "n_eligible", "n_candidates"]
    write_table(log_df[log_cols], "window_log", "Selected window per outer fold", note)
    write_table(pd.concat(scores, ignore_index=True), "inner_scores", "Inner leave-one-cell-out scores", note)
    pair_note = (
        "Each pair compared on the held-out traces both models answered, each model at its own "
        f"selected window. Decision rule fixed in advance: IC helps only if the IC model has lower "
        f"RMSE in at least {IC_HELPS_MIN_CELLS} of 8 held-out cells (one-sided sign test). In regime "
        "`any` the two models may use different windows, so a gain there can come partly from a longer "
        "window; the `wNNN` rows compare at equal width."
    )
    pair_df = pd.DataFrame(pair_rows)
    write_table(pair_df, "paired_ic", "Paired comparison: IC model vs control", pair_note)
    pc_cols = ["ic_model", "base_model", "regime", "cell", "n", "rmse_base", "rmse_ic", "ic_better"]
    write_table(pd.concat(pair_cells, ignore_index=True)[pc_cols], "paired_ic_per_cell", "Paired comparison per cell", pair_note)

    common = log_df[(log_df.regime == "any")].groupby("model").apply(
        lambda g: g.groupby(["v1", "v2"]).size().idxmax(), include_groups=False
    )
    plots.charge_curves(curves, {m: Win(*common[m]) for m in ("M1", "M2")})

    cols = ["model", "regime", "rmse", "macro_rmse", "mae", "max_abs", "answer_rate", "median_window_s", "windows"]
    print(pooled_df[cols].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print()
    print(pair_df.to_string(index=False, float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main()
