import numpy as np
import pytest

from soh.degrade import CASES, NATIVE_PERIOD_S, SEEDS, Case, decimate, degrade, quantize, trace_rng


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
