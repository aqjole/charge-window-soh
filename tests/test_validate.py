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


# --- calibrated GPR intervals ---------------------------------------------------------

from soh.validate import calibration_factor  # noqa: E402


def gaussian_preds(sigma_true, std, n=4000, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        dict(cell=1, reason="OK", c0=700.0, capacity=700.0, pred=700.0 + rng.normal(0, sigma_true, n), std=std)
    )


def test_calibration_factor_scales_std_to_the_errors():
    p = gaussian_preds(sigma_true=2.0, std=1.0)
    k = calibration_factor(p)
    assert k == pytest.approx(2.0, rel=0.05)
    assert calibration_factor(gaussian_preds(sigma_true=0.5, std=1.0)) == pytest.approx(0.5, rel=0.05)  # may narrow
    m = metrics(p.assign(std_cal=p["std"] * k))
    assert m["coverage95"] < 0.70
    assert m["coverage95_cal"] == pytest.approx(0.95, abs=0.005)
    assert m["interval_width_cal"] == pytest.approx(k * m["interval_width"])


def test_calibration_factor_ignores_unanswered_and_needs_answers():
    p = gaussian_preds(sigma_true=2.0, std=1.0, n=100)
    q = p.copy()
    q.loc[:9, "pred"] = np.nan
    assert calibration_factor(q) == calibration_factor(p.iloc[10:])
    assert np.isnan(calibration_factor(p.assign(pred=np.nan)))


def test_held_out_cell_never_sets_its_own_calibration():
    win = Win(3.6, 3.8)
    feats = {win: synthetic_table(noise=0.3)}
    base = inner_scores(feats, "M3").set_index("fold").k95
    assert base.notna().all()
    feats[win] = feats[win].copy()
    feats[win].loc[feats[win].cell == 3, "capacity"] += 5.0  # cell 3 badly off
    after = inner_scores(feats, "M3").set_index("fold").k95
    assert after[3] == pytest.approx(base[3], abs=1e-6)
    assert (after.drop(3) > base.drop(3)).all()  # every other fold saw it


def test_outer_std_scaled_by_its_folds_factor():
    feats = {Win(3.6, 3.8): synthetic_table(noise=0.3)}
    pooled, _, log, _, preds = nested(feats, "M3", regimes=("any",))
    pred, k = preds["any"], log[0].set_index("fold").k95
    np.testing.assert_allclose(pred.std_cal, pred["std"] * pred.cell.map(k))
    assert {"coverage95_cal", "interval_width_cal"} <= set(pooled[0])
    assert "coverage95_cal" not in metrics(nested(feats, "M1", regimes=("any",))[4]["any"])


# --- offset-augmented training (M6) ----------------------------------------------------

from soh.load import Curve  # noqa: E402
from soh.validate import aug_offsets_mv, feature_table, fit_model, originals, AUG_COPIES, AUG_MAX_MV  # noqa: E402


def augmented(df):
    """Synthetic table plus AUG_COPIES copies per row; copies carry a junk dq."""
    copies = [df.assign(aug=k, dq=df.dq + 1e3 * k) for k in range(1, AUG_COPIES + 1)]
    return pd.concat([df.assign(aug=0), *copies], ignore_index=True)


def spy_models(monkeypatch):
    from soh import validate

    seen = {}

    def spy(name):
        class Spy:
            def fit(self, X, y):
                seen.setdefault(name, []).append(X[:, 0].copy())
                return self

            def predict(self, X):
                return np.zeros(len(X))

        return Spy

    monkeypatch.setitem(validate.MODELS, "PLAIN", Spec(("dq",), spy("PLAIN")))
    monkeypatch.setitem(validate.MODELS, "AUG", Spec(("dq",), spy("AUG"), augment=True))
    return seen


def test_only_augmented_models_train_on_copies(monkeypatch):
    seen = spy_models(monkeypatch)
    df = augmented(synthetic_table())
    for name in ("PLAIN", "AUG"):
        pred = outer_loco(df, name)
        assert len(pred) == 80 and (pred.aug == 0).all()
    assert [len(x) for x in seen["PLAIN"]] == [70] * 8
    assert all((x < 1e3).all() for x in seen["PLAIN"])
    assert [len(x) for x in seen["AUG"]] == [70 * (1 + AUG_COPIES)] * 8


def test_augmented_copies_of_held_out_cell_never_train(monkeypatch):
    seen = spy_models(monkeypatch)
    df = augmented(synthetic_table())
    df.loc[(df.cell == 3) & (df.aug > 0), "dq"] = -1.0
    fit_model(df, "AUG", [c for c in range(1, 9) if c != 3])
    assert not (seen["AUG"][0] == -1.0).any()


def test_inner_scores_identical_with_or_without_copies_for_plain_models():
    feats = multi_window_features({Win(3.6, 3.8): 0.5, Win(3.5, 3.6): 2.0})
    plain = inner_scores(feats, "M1")
    aug = inner_scores({w: augmented(d) for w, d in feats.items()}, "M1")
    pd.testing.assert_frame_equal(plain, aug)


def toy_curve(cell, cycle):
    t = np.arange(0.0, 3000.0)
    return Curve(cell, cycle, t, 3.4 + 0.75 * np.sqrt(t / 3000.0), 700.0, 735.0)


def test_aug_offsets_fixed_per_trace_and_in_range():
    a, b = aug_offsets_mv(toy_curve(1, 100)), aug_offsets_mv(toy_curve(1, 100))
    np.testing.assert_array_equal(a, b)
    assert len(a) == AUG_COPIES and (np.abs(a) <= AUG_MAX_MV).all()
    assert not np.array_equal(a, aug_offsets_mv(toy_curve(1, 200)))


def test_augmented_feature_table_applies_each_copys_offset():
    curves = [toy_curve(1, 0), toy_curve(2, 0)]
    win = Win(3.6, 3.8)
    plain, aug = feature_table(curves, win), feature_table(curves, win, augment=True)
    pd.testing.assert_frame_equal(originals(aug).reset_index(drop=True), plain)
    assert len(aug) == len(curves) * (2 + AUG_COPIES) and (aug.reason == "OK").all()
    for c in curves:
        rows = aug[(aug.cell == c.cell) & (aug.aug <= AUG_COPIES)].sort_values("aug")
        dq0, dq_copies = rows.dq.iloc[0], rows.dq.iloc[1:].to_numpy()
        np.testing.assert_array_equal(np.sign(dq0 - dq_copies), np.sign(aug_offsets_mv(c)))


# --- noise copy and curve model (M8) ---------------------------------------------------

from soh.models import CURVE_COLS, HalvesPlusCurve  # noqa: E402
from soh.validate import NOISE_COPY, noise_copy, training_rows  # noqa: E402


def test_noise_copy_is_degraded_and_fixed_per_trace():
    c = toy_curve(1, 100)
    for i in range(6):
        (t, v), (t2, v2) = noise_copy(c, i), noise_copy(c, i)
        np.testing.assert_array_equal(v, v2)
        assert len(t) < len(c.t) or not np.array_equal(v, c.v[: len(v)])
    assert not np.array_equal(noise_copy(c, 0)[1], noise_copy(toy_curve(1, 200), 0)[1])


def test_noise_copy_seed_is_never_a_degraded_test_seed():
    from soh.degrade import SEEDS
    from soh.validate import NOISE_COPY_SEED

    assert NOISE_COPY_SEED not in SEEDS


def test_each_augment_mode_trains_on_its_own_copies(monkeypatch):
    from soh import validate

    df = pd.concat([synthetic_table().assign(aug=k) for k in range(NOISE_COPY + 1)], ignore_index=True)
    monkeypatch.setitem(validate.MODELS, "NOISE", Spec(("dq",), object, augment="noise"))
    monkeypatch.setitem(validate.MODELS, "AUG", Spec(("dq",), object, augment=True))
    monkeypatch.setitem(validate.MODELS, "PLAIN", Spec(("dq",), object))
    assert set(training_rows(df, "PLAIN").aug) == {0}
    assert set(training_rows(df, "AUG").aug) == set(range(AUG_COPIES + 1))
    assert set(training_rows(df, "NOISE").aug) == {0, 1, NOISE_COPY}


def test_feature_table_carries_the_window_curve():
    win = Win(3.6, 3.8)
    df = feature_table([toy_curve(1, 0)], win)
    seg = df[list(CURVE_COLS)].to_numpy()[0]
    half = len(seg) // 2
    assert seg.sum() == pytest.approx(df.dq.iloc[0])
    assert (seg[:half].sum(), seg[half:].sum()) == (pytest.approx(df.dq_a.iloc[0]), pytest.approx(df.dq_b.iloc[0]))


def test_halves_plus_curve_is_exact_on_a_linear_relation_of_the_halves():
    rng = np.random.default_rng(0)
    X = rng.uniform(5, 15, (60, 16))
    y = 100 + 2 * X[:, :8].sum(1) + 3 * X[:, 8:].sum(1)
    m = HalvesPlusCurve().fit(X, y)
    mu, sd = m.predict(X[:5], return_std=True)
    np.testing.assert_allclose(mu, y[:5], atol=1e-6)
    assert (sd >= 0).all() and np.allclose(m.predict(X[:5]), mu)
