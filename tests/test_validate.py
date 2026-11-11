import numpy as np
import pandas as pd
import pytest

from soh.validate import loco as outer_loco, metrics


def synthetic_table(noise=0.0, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for cell in range(1, 9):
        c0 = 735.0 + cell
        for k in range(10):
            cap = c0 * (1 - 0.01 * k)
            dq = 0.1 * cap + rng.normal(0, noise)
            rows.append(dict(cell=cell, cycle=100 * k, reason="OK", dq=dq, duration_s=dq * 3600 / 740, capacity=cap, c0=c0))
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


# --- nested selection -----------------------------------------------------------------

from soh.validate import SelectionError, Win, inner_scores, nested, select, window_grid  # noqa: E402


def test_grid_has_17_windows_for_4v2_cutoff():
    grid = window_grid(4.2)
    assert len(grid) == 17
    assert max(w.v2 for w in grid) == pytest.approx(4.1)
    assert Win(3.7, 4.1) in grid and Win(3.8, 4.2) not in grid


def multi_window_features(noise_by_window, seed=0):
    """Same labels for every window; dq noise level differs per window."""
    feats = {}
    for i, (win, noise) in enumerate(noise_by_window.items()):
        feats[win] = synthetic_table(noise=noise, seed=seed + i)
    return feats


def scores_frame(rows):
    return pd.DataFrame(
        [dict(model="M1", fold=f, v1=v1, v2=v2, width_mv=round(1000 * (v2 - v1)), score=s, answer_rate=a)
         for f, v1, v2, s, a in rows]
    )


def test_select_picks_lowest_score():
    s = scores_frame([(1, 3.5, 3.6, 2.0, 1.0), (1, 3.6, 3.8, 1.0, 1.0)])
    assert select(s, "any").iloc[0][["v1", "v2"]].tolist() == [3.6, 3.8]


def test_select_tie_goes_to_narrower_then_lower_v1():
    s = scores_frame([(1, 3.7, 3.9, 1.0, 1.0), (1, 3.6, 3.7, 1.0, 1.0), (1, 3.5, 3.6, 1.0, 1.0)])
    assert select(s, "any").iloc[0][["v1", "v2"]].tolist() == [3.5, 3.6]


def test_select_skips_windows_below_answer_rate():
    s = scores_frame([(1, 3.5, 3.6, 0.1, 0.94), (1, 3.6, 3.8, 1.0, 0.95)])
    assert select(s, "any").iloc[0][["v1", "v2"]].tolist() == [3.6, 3.8]


def test_select_raises_when_nothing_eligible():
    s = scores_frame([(1, 3.5, 3.6, 0.1, 0.5)])
    with pytest.raises(SelectionError):
        select(s, "any")


def test_width_regime_restricts_grid():
    s = scores_frame([(1, 3.5, 3.6, 2.0, 1.0), (1, 3.6, 3.8, 1.0, 1.0)])
    assert select(s, "w100").iloc[0][["v1", "v2"]].tolist() == [3.5, 3.6]


def test_nested_finds_the_informative_window():
    good, bad = Win(3.6, 3.8), Win(3.5, 3.6)
    feats = multi_window_features({good: 0.05, bad: 5.0})
    _, _, log, _ = nested(feats, "M1", regimes=("any",))
    assert (log[0][["v1", "v2"]].to_numpy() == [good.v1, good.v2]).all()


def test_held_out_cell_never_influences_its_fold_selection():
    good, bad = Win(3.6, 3.8), Win(3.5, 3.6)
    feats = multi_window_features({good: 0.5, bad: 0.6})
    base = select(inner_scores(feats, "M1"), "any")
    # Make cell 3 useless at the "good" window only: fold 3's choice must not move.
    feats[good] = feats[good].copy()
    feats[good].loc[feats[good].cell == 3, "dq"] = 1e6
    after = select(inner_scores(feats, "M1"), "any")
    pd.testing.assert_series_equal(base[base.fold == 3].v1, after[after.fold == 3].v1)
    pd.testing.assert_series_equal(base[base.fold == 3].v2, after[after.fold == 3].v2)
    assert (after[after.fold != 3].v1 == bad.v1).all()  # sanity: other folds did see the damage
