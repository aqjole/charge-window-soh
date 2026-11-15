import numpy as np
import pandas as pd
import pytest

from soh.degrade import (
    AVG_CHARGES,
    CASES,
    MAIN_DETECTOR,
    NATIVE_PERIOD_S,
    SEEDS,
    Case,
    average_charges,
    decimate,
    degrade,
    quantize,
    summarize_avg,
    trace_rng,
)


def trace(n=3000):
    t = np.arange(n, dtype=float)
    return t, 3.4 + 0.25e-3 * t


def test_clean_case_is_identity():
    t, v = trace()
    td, vd = degrade(t, v, Case("clean", "clean"), trace_rng(0, 1, 0))
    np.testing.assert_array_equal(td, t)
    np.testing.assert_array_equal(vd, v)


def test_same_seed_same_trace_and_seeds_differ():
    t, v = trace()
    case = Case("c", "combined", noise_mv=2, lsb_mv=1, period_s=10)
    a = degrade(t, v, case, trace_rng(3, 2, 500))
    b = degrade(t, v, case, trace_rng(3, 2, 500))
    c = degrade(t, v, case, trace_rng(4, 2, 500))
    np.testing.assert_array_equal(a[0], b[0])
    np.testing.assert_array_equal(a[1], b[1])
    assert len(a[1]) != len(c[1]) or not np.array_equal(a[1], c[1])


def test_randomness_depends_on_trace_not_order():
    t, v = trace()
    case = Case("n", "noise", noise_mv=5)
    first = degrade(t, v, case, trace_rng(0, 1, 100))[1]
    degrade(t, v, case, trace_rng(0, 7, 900))  # another trace in between
    np.testing.assert_array_equal(first, degrade(t, v, case, trace_rng(0, 1, 100))[1])


def test_quantize_rounds_to_lsb():
    v = np.array([3.6004, 3.6005001, 3.6026, 3.6074])
    np.testing.assert_allclose(quantize(v, 0.005), [3.600, 3.600, 3.605, 3.605])
    np.testing.assert_allclose(quantize(v, 0.001), [3.600, 3.601, 3.603, 3.607])
    np.testing.assert_array_equal(quantize(v, 0.0), v)


def test_quantized_values_lie_on_grid():
    t, v = trace()
    _, vd = degrade(t, v, Case("q", "lsb", lsb_mv=5), trace_rng(0, 1, 0))
    np.testing.assert_allclose(vd / 0.005, np.round(vd / 0.005), atol=1e-9)
    assert np.abs(vd - v).max() <= 0.0025 + 1e-12


def test_decimation_spacing_and_phase():
    t, _ = trace()
    idx = decimate(t, 10.0, 3.0)
    np.testing.assert_array_equal(t[idx][:3], [3.0, 13.0, 23.0])
    assert np.all(np.diff(t[idx]) == 10.0)


def test_decimation_holds_last_sample_before_tick():
    t = np.array([0.0, 0.7, 1.9, 3.2, 4.1, 5.5])
    np.testing.assert_array_equal(decimate(t, 2.0, 0.5), [0, 2, 4])  # ticks 0.5, 2.5, 4.5


def test_decimation_at_native_period_keeps_everything():
    t, _ = trace(100)
    np.testing.assert_array_equal(decimate(t, NATIVE_PERIOD_S, 0.4), np.arange(100))


def test_noise_and_offset_statistics():
    t, v = trace(20000)
    _, vd = degrade(t, v, Case("n", "noise", noise_mv=2, offset_mv=5), trace_rng(0, 1, 0))
    r = (vd - v) * 1000
    assert r.mean() == pytest.approx(5.0, abs=0.05)
    assert r.std() == pytest.approx(2.0, rel=0.03)


def test_seeds_only_where_random():
    by_name = {c.name: c for c in CASES}
    assert by_name["noise 2 mV"].seeds == SEEDS and len(SEEDS) == 20
    assert by_name["period 10 s"].seeds == SEEDS
    assert by_name["combined"].seeds == SEEDS
    for name in ("clean", "offset -5 mV", "LSB 5 mV", "period 1 s"):
        assert by_name[name].seeds == (0,)


def fake_preds(case="noise 2 mV", model="M1", sigma=1.0, bias=0.0, n_cycles=40):
    """Predictions with capacity 100 and c0 100, so an error in mAh is one in SOH points."""
    rng = np.random.default_rng(0)
    rows = [
        dict(case=case, detector=MAIN_DETECTOR, model=model, seed=s, cell=cell, cycle=cyc,
             pred=100.0 + bias + sigma * rng.normal(), capacity=100.0, c0=100.0)
        for s in SEEDS for cell in range(1, 9) for cyc in range(n_cycles)
    ]
    return pd.DataFrame(rows)


def test_average_charges_blocks_and_unanswered():
    p = pd.DataFrame(dict(case="c", model="M1", cell=1, cycle=0, seed=range(10), capacity=100.0, c0=100.0,
                          pred=[1.0, 2.0, 3.0, 4.0, np.nan] + [np.nan] * 5))
    a = average_charges(p, 5).set_index("block")
    assert a.pred[0] == pytest.approx(2.5) and a.n_answered[0] == 4
    assert np.isnan(a.pred[1]) and a.n_answered[1] == 0


def avg_row(preds, case, model):
    return summarize_avg(preds).set_index(["case", "model"]).loc[(case, model)]


def test_averaging_shrinks_random_error_only():
    noisy = avg_row(fake_preds(sigma=1.0), "noise 2 mV", "M1")
    assert AVG_CHARGES == 5 and noisy.n_blocks == 4
    assert noisy.rmse_single == pytest.approx(1.0, rel=0.05)
    assert noisy.rmse_avg == pytest.approx(1.0 / np.sqrt(5), rel=0.05)
    assert noisy.max_abs_avg < noisy.max_abs_single
    biased = avg_row(fake_preds(sigma=0.0, bias=2.0), "noise 2 mV", "M1")
    assert biased.rmse_avg == pytest.approx(biased.rmse_single) == pytest.approx(2.0)
    assert biased.worst_cell_avg == pytest.approx(biased.worst_cell_single)


def test_averaging_reports_models_without_answers():
    p = fake_preds(case="period 60 s", model="M2").assign(pred=np.nan)
    row = avg_row(p, "period 60 s", "M2")
    assert row.n_blocks == 4 and np.isnan(row.rmse_single) and np.isnan(row.rmse_avg)
