"""Outer leave-one-cell-out validation.

One window fixed in advance (3.6-4.0 V). The table is labelled preliminary; the
reported numbers come from nested window selection (commit 3).

A model answers a trace only when its features exist (reason OK). Training uses
answered training traces; error metrics use answered held-out traces; every
unanswered trace is counted by reason.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from soh.features import NO_ESTIMATE_REASONS, Reason, detect_window
from soh.load import N_CELLS, Curve, load
from soh.models import MODELS
from soh.report import write_table

FIXED_WINDOW = (3.6, 4.0)


def feature_table(curves: list[Curve], v1: float, v2: float) -> pd.DataFrame:
    rows = []
    for c in curves:
        w = detect_window(c.t, c.v, v1, v2)
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


def outer_loco(df: pd.DataFrame, model: str) -> pd.DataFrame:
    """Predict each cell from a model fit on the other seven.

    Returns all rows of `df` with `pred` in mAh (NaN where the model gives no estimate).
    """
    cols, factory = MODELS[model]
    answered = df.reason == Reason.OK.value
    X = lambda d: d[list(cols)].to_numpy() if cols else np.zeros((len(d), 1))  # noqa: E731
    out = []
    for held in range(1, N_CELLS + 1):
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


def per_cell(pred: pd.DataFrame, model: str) -> pd.DataFrame:
    rows = []
    for cell, g in pred.groupby("cell"):
        m = metrics(g)
        del m["macro_rmse"]  # equals rmse for a single cell
        rows.append(dict(model=model, cell=int(cell), **m))
    return pd.DataFrame(rows)


def main() -> None:
    curves, _ = load()
    v1, v2 = FIXED_WINDOW
    df = feature_table(curves, v1, v2)

    pooled, cells = [], []
    for name in MODELS:
        pred = outer_loco(df, name)
        ok = df.reason == Reason.OK.value
        pooled.append(dict(model=name, **metrics(pred), median_window_s=float(df.duration_s[ok].median())))
        cells.append(per_cell(pred, name))

    note = (
        f"Preliminary: one window fixed in advance at {v1:.1f}-{v2:.1f} V, outer leave-one-cell-out. "
        "Errors in SOH percentage points on answered traces; n_<REASON> counts traces with no estimate. "
        "Not the reported number (nested selection comes in commit 3)."
    )
    write_table(pd.DataFrame(pooled), "clean_fixed_window", "Clean data, fixed window", note)
    write_table(pd.concat(cells, ignore_index=True), "clean_fixed_window_per_cell", "Per cell", note)
    print(pd.DataFrame(pooled).to_string(index=False, float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main()
