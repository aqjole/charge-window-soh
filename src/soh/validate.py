"""Outer leave-one-cell-out validation.

Commit 1 (MVP): one window fixed in advance (3.6-4.0 V). The table is labelled
preliminary; the reported numbers come from nested window selection (commit 3).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from soh.features import window_dq
from soh.load import N_CELLS, Curve, load
from soh.models import MODELS
from soh.report import write_table

FIXED_WINDOW = (3.6, 4.0)


def feature_table(curves: list[Curve], v1: float, v2: float) -> pd.DataFrame:
    rows = []
    for c in curves:
        dq, dur = window_dq(c.t, c.v, v1, v2)
        rows.append(
            dict(cell=c.cell, cycle=c.cycle, dq=dq, duration_s=dur, capacity=c.capacity_mah, c0=c.c0_mah)
        )
    return pd.DataFrame(rows)


def outer_loco(df: pd.DataFrame, model: str) -> pd.DataFrame:
    """Predict each cell from a model fit on the other seven. Adds `pred` in mAh."""
    cols, factory = MODELS[model]
    out = []
    for held in range(1, N_CELLS + 1):
        train, test = df[df.cell != held], df[df.cell == held].copy()
        X = lambda d: d[list(cols)].to_numpy() if cols else np.zeros((len(d), 1))  # noqa: E731
        m = factory().fit(X(train), train.capacity.to_numpy())
        test["pred"] = m.predict(X(test))
        out.append(test)
    return pd.concat(out, ignore_index=True)


def metrics(pred: pd.DataFrame) -> dict[str, float]:
    """Errors in SOH percentage points: 100 * (pred - capacity) / c0."""
    err = 100.0 * (pred.pred - pred.capacity) / pred.c0
    per_cell_rmse = err.groupby(pred.cell).apply(lambda e: np.sqrt(np.mean(e**2)))
    return dict(
        rmse=float(np.sqrt(np.mean(err**2))),
        macro_rmse=float(per_cell_rmse.mean()),
        mae=float(np.mean(np.abs(err))),
        max_abs=float(np.max(np.abs(err))),
        n=int(len(err)),
    )


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
    if df.dq.isna().any():
        missing = df[df.dq.isna()][["cell", "cycle"]].to_records(index=False).tolist()
        raise SystemExit(f"window {v1}-{v2} V not completed on {missing}; handled from commit 2")

    pooled, cells = [], []
    for name in MODELS:
        pred = outer_loco(df, name)
        pooled.append(dict(model=name, **metrics(pred), median_window_s=float(df.duration_s.median())))
        cells.append(per_cell(pred, name))

    note = (
        f"Preliminary: one window fixed in advance at {v1:.1f}-{v2:.1f} V, outer leave-one-cell-out. "
        "Errors in SOH percentage points. Not the reported number (nested selection comes in commit 3)."
    )
    write_table(pd.DataFrame(pooled), "clean_fixed_window", "Clean data, fixed window", note)
    write_table(pd.concat(cells, ignore_index=True), "clean_fixed_window_per_cell", "Per cell", note)
    print(pd.DataFrame(pooled).to_string(index=False, float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main()
