"""Nested leave-one-cell-out validation with window selection.

Outer loop: leave one cell out (8 folds). Inside each fold, every model picks its
own window from a fixed grid by inner leave-one-cell-out on the 7 training cells:

- score = mean over inner held-out cells of that cell's RMSE (SOH points);
- eligible only if the model answers >= MIN_ANSWER_RATE of inner held-out traces;
- ties go to the narrower window, then the lower V1;
- no eligible window -> SelectionError (stop and ask).

The held-out cell is never used for any choice. Width-frontier regimes repeat the
selection with the grid restricted to one width, reusing the cached inner scores.

A model answers a trace only when its features exist (reason OK). Training uses
answered training traces; error metrics use answered held-out traces; every
unanswered trace is counted by reason.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from soh.features import NO_ESTIMATE_REASONS, Reason, detect_window
from soh.load import Curve, load
from soh.models import MODELS
from soh.report import write_table

V1_GRID = (3.5, 3.6, 3.7, 3.8, 3.9)
WIDTHS_MV = (100, 200, 300, 400)
CUTOFF_MARGIN_V = 0.050
MIN_ANSWER_RATE = 0.95
REGIMES = ("any",) + tuple(f"w{w}" for w in WIDTHS_MV)


class SelectionError(RuntimeError):
    """No window is eligible. The data contradicts the spec; stop and ask."""


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
        rows.append(
            dict(
                cell=c.cell,
                cycle=c.cycle,
                reason=w.reason.value,
                dq=w.dq,
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
    (NaN where the model gives no estimate).
    """
    cols, factory = MODELS[model]
    cells = sorted(df.cell.unique()) if cells is None else sorted(cells)
    df = df[df.cell.isin(cells)]
    answered = df.reason == Reason.OK.value
    X = lambda d: d[list(cols)].to_numpy() if cols else np.zeros((len(d), 1))  # noqa: E731
    out = []
    for held in cells:
        train = df[(df.cell != held) & answered]
        test = df[df.cell == held].copy()
        m = factory().fit(X(train), train.capacity.to_numpy())
        test["pred"] = np.nan
        ok = test.reason == Reason.OK.value
        if ok.any():
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
    """Return (pooled rows, per-cell rows, window log rows, inner scores) for one model."""
    scores = inner_scores(features, model)
    pooled, cells, log = [], [], []
    for regime in regimes:
        chosen = select(scores, regime)
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
    return pooled, cells, log, scores


def main() -> None:
    curves, audit = load()
    grid = window_grid(round(audit.cutoff_v[0], 2))
    features = {w: feature_table(curves, w) for w in grid}
    print(f"{len(grid)} windows: {', '.join(map(str, grid))}")

    pooled, cells, log, scores = [], [], [], []
    for name in MODELS:
        p, c, lg, s = nested(features, name)
        pooled += p
        cells += c
        log += lg
        scores.append(s)

    note = (
        "Nested leave-one-cell-out: each model picks its window inside each outer fold by inner "
        "leave-one-cell-out on the 7 training cells. Regime `any` searches the full grid; `wNNN` "
        "restricts it to one width (mV). Errors in SOH percentage points on answered traces; "
        "n_<REASON> counts traces with no estimate."
    )
    pooled_df = pd.DataFrame(pooled)
    write_table(pooled_df, "clean_nested", "Clean data, nested validation", note)
    write_table(pd.DataFrame(cells), "clean_nested_per_cell", "Clean data, nested validation, per cell", note)
    log_df = pd.concat(log, ignore_index=True)
    log_cols = ["model", "regime", "fold", "v1", "v2", "width_mv", "inner_score", "inner_answer_rate", "n_eligible", "n_candidates"]
    write_table(log_df[log_cols], "window_log", "Selected window per outer fold", note)
    write_table(pd.concat(scores, ignore_index=True), "inner_scores", "Inner leave-one-cell-out scores", note)

    cols = ["model", "regime", "rmse", "macro_rmse", "mae", "max_abs", "answer_rate", "median_window_s", "windows"]
    print(pooled_df[cols].to_string(index=False, float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main()
