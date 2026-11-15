import numpy as np
import pandas as pd
import pytest

from soh.models import Spec
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

    monkeypatch.setitem(validate.MODELS, "SPY", Spec(("dq",), Spy))
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
    _, _, log, _, _ = nested(feats, "M1", regimes=("any",))
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


# --- IC model: no fallback, paired comparison ---------------------------------------

from soh.validate import paired, sign_test_p  # noqa: E402


def with_ic(df, rng_seed=0):
    rng = np.random.default_rng(rng_seed)
    df = df.copy()
    df["ic_reason"] = "OK"
    df["ic_peak_h"] = rng.normal(3000, 10, len(df))
    df["ic_peak_v"] = rng.normal(3.9, 0.01, len(df))
    return df


def test_m2_gives_no_estimate_without_ic_and_counts_reason():
    df = with_ic(synthetic_table())
    df.loc[[0, 1], "ic_reason"] = ["IC_EDGE", "IC_SPARSE"]
    df.loc[[0, 1], ["ic_peak_h", "ic_peak_v"]] = np.nan
    m2 = outer_loco(df, "M2")
    m1 = outer_loco(df, "M1")
    assert m2.loc[m2.cycle.isin([0, 100]) & (m2.cell == 1), "pred"].isna().all()
    assert m1.pred.notna().all()  # M1 is unaffected by IC reasons
    m = metrics(m2)
    assert (m["n_IC_EDGE"], m["n_IC_SPARSE"], m["n"]) == (1, 1, 78)


def test_m2_window_reason_takes_precedence():
    df = with_ic(synthetic_table())
    df.loc[0, ["reason", "ic_reason"]] = ["GAP", "GAP"]
    df.loc[0, ["dq", "ic_peak_h", "ic_peak_v"]] = np.nan
    assert metrics(outer_loco(df, "M2"))["n_GAP"] == 1


def test_sign_test_p_values():
    assert sign_test_p(7, 8) == pytest.approx(9 / 256)
    assert sign_test_p(8, 8) == pytest.approx(1 / 256)
    assert sign_test_p(0, 8) == 1.0


def test_paired_uses_only_common_traces_and_applies_rule():
    base = synthetic_table().assign(pred=lambda d: d.capacity + 7.0)  # 1 point-ish error
    ic = base.assign(pred=lambda d: d.capacity + 3.5)
    ic.loc[ic.cell == 8, "pred"] = ic.loc[ic.cell == 8, "capacity"] + 20.0  # worse on one cell
    ic.loc[0, "pred"] = np.nan  # unanswered by IC model -> excluded from both
    summ, per_cell = paired(ic, base)
    assert summ["n_common"] == 79
    assert summ["cells_model_better"] == 7
    assert summ["verdict"] == "helps"
    ic.loc[ic.cell == 7, "pred"] = ic.loc[ic.cell == 7, "capacity"] + 20.0
    assert paired(ic, base)[0]["verdict"] == "no detectable gain"


def test_window_with_no_answered_training_traces():
    df = with_ic(synthetic_table())
    df.loc[df.cell != 1, "ic_reason"] = "IC_EDGE"
    pred = outer_loco(df, "M2")
    m = metrics(pred)
    assert m["n"] == 0
    assert m["n_NO_TRAIN"] == 10  # cell 1 has IC but nothing to train on
    assert m["n_IC_EDGE"] == 70


# --- shared inner fits, GPR models, coverage --------------------------------------------

from soh.validate import Z95  # noqa: E402


def test_shared_pair_fits_equal_plain_inner_loco():
    feats = multi_window_features({Win(3.6, 3.8): 0.5, Win(3.5, 3.6): 2.0})
    scores = inner_scores(feats, "M1")
    for win, df in feats.items():
        for held in range(1, 9):
            plain = metrics(outer_loco(df, "M1", [c for c in range(1, 9) if c != held]))["macro_rmse"]
            row = scores[(scores.fold == held) & (scores.v1 == win.v1) & (scores.v2 == win.v2)]
            assert row.score.item() == pytest.approx(plain, rel=1e-12)


def test_coverage_and_interval_width():
    pred = pd.DataFrame(
        dict(
            cell=[1] * 4, reason=["OK"] * 4, c0=[700.0] * 4, capacity=[700.0] * 4,
            pred=[700.0, 701.0, 703.0, 690.0], std=[1.0] * 4,
        )
    )
    m = metrics(pred)
    assert m["coverage95"] == pytest.approx(0.5)  # |err| 0, 1 inside 1.96; 3, 10 outside
    assert m["interval_width"] == pytest.approx(100 * 2 * Z95 / 700)


def test_point_models_report_no_coverage():
    assert "coverage95" not in metrics(outer_loco(synthetic_table(), "M1"))


def test_m3_fits_smooth_relation_with_calibrated_band():
    pred = outer_loco(synthetic_table(noise=0.2), "M3")
    m = metrics(pred)
    assert m["answer_rate"] == 1.0
    assert m["rmse"] < 0.5
    assert m["coverage95"] >= 0.85
    assert (pred["std"] > 0).all()


def test_gpr_is_deterministic():
    df = synthetic_table(noise=0.2)
    a, b = outer_loco(df, "M3"), outer_loco(df, "M3")
    # Fixed seed -> same optimum. Threaded BLAS (Accelerate) may differ at ~1e-10 mAh,
    # far below the 4-decimal precision of the result tables.
    np.testing.assert_allclose(a.pred, b.pred, rtol=0, atol=1e-6)
    np.testing.assert_allclose(a["std"], b["std"], rtol=0, atol=1e-6)


def test_m4_gives_no_estimate_without_ic():
    df = with_ic(synthetic_table(noise=0.2))
    df.loc[[0, 1], "ic_reason"] = ["IC_EDGE", "IC_SPARSE"]
    df.loc[[0, 1], ["ic_peak_h", "ic_peak_v"]] = np.nan
    m = metrics(outer_loco(df, "M4"))
    assert (m["n_IC_EDGE"], m["n_IC_SPARSE"], m["n"]) == (1, 1, 78)
