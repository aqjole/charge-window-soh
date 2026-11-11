import numpy as np
import pandas as pd
import pytest

from soh.validate import metrics, outer_loco


def synthetic_table(noise=0.0, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for cell in range(1, 9):
        c0 = 735.0 + cell
        for k in range(10):
            cap = c0 * (1 - 0.01 * k)
            rows.append(dict(cell=cell, cycle=100 * k, reason="OK", dq=0.1 * cap + rng.normal(0, noise), capacity=cap, c0=c0))
    return pd.DataFrame(rows)


def test_m1_recovers_exact_linear_relation():
    pred = outer_loco(synthetic_table(), "M1")
    assert metrics(pred)["rmse"] == pytest.approx(0.0, abs=1e-9)


def test_held_out_cell_never_in_training(monkeypatch):
    df = synthetic_table()
    seen = []

    from soh import validate

    class Spy:
        def fit(self, X, y):
            seen.append(len(y))
            return self

        def predict(self, X):
            return np.zeros(len(X))

    monkeypatch.setitem(validate.MODELS, "SPY", (("dq",), Spy))
    pred = outer_loco(df, "SPY")
    assert seen == [70] * 8
    assert len(pred) == 80


def test_metrics_in_soh_points():
    pred = pd.DataFrame(
        dict(cell=[1, 1], reason=["OK", "OK"], capacity=[700.0, 700.0], pred=[707.0, 693.0], c0=[700.0, 700.0])
    )
    m = metrics(pred)
    assert m["rmse"] == pytest.approx(1.0)
    assert m["mae"] == pytest.approx(1.0)
    assert m["max_abs"] == pytest.approx(1.0)
    assert m["answer_rate"] == 1.0


def test_no_estimate_rows_are_counted_not_dropped():
    df = synthetic_table()
    df.loc[[0, 1, 2], "reason"] = ["NOT_ARMED", "NO_V2", "GAP"]
    df.loc[[0, 1, 2], "dq"] = np.nan
    pred = outer_loco(df, "M1")
    assert len(pred) == len(df)
    m = metrics(pred)
    assert (m["n"], m["n_total"]) == (77, 80)
    assert (m["n_NOT_ARMED"], m["n_NO_V2"], m["n_GAP"]) == (1, 1, 1)
    assert m["answer_rate"] == pytest.approx(77 / 80)
    assert m["rmse"] == pytest.approx(0.0, abs=1e-9)


def test_unanswered_training_rows_are_not_fitted(monkeypatch):
    df = synthetic_table()
    df.loc[df.cell == 2, "reason"] = "NO_V2"
    df.loc[df.cell == 2, "dq"] = np.nan  # would crash LinearRegression if fitted
    pred = outer_loco(df, "M1")
    assert pred[pred.cell == 2].pred.isna().all()
    assert pred[pred.cell != 2].pred.notna().all()
