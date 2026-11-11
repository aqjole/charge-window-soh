import numpy as np
import pytest

from soh.features import crossing_time, window_dq


def linear_trace(v_start=3.0, v_end=4.2, rate_v_per_s=0.001, dt=1.0):
    t = np.arange(0.0, (v_end - v_start) / rate_v_per_s + dt, dt)
    return t, v_start + rate_v_per_s * t


def test_crossing_interpolates_between_samples():
    t = np.array([0.0, 10.0, 20.0])
    v = np.array([3.50, 3.60, 3.70])
    tc, k = crossing_time(t, v, 3.65)
    assert k == 2
    assert tc == pytest.approx(15.0)


def test_crossing_on_exact_sample():
    t = np.array([0.0, 10.0, 20.0])
    v = np.array([3.50, 3.60, 3.70])
    tc, k = crossing_time(t, v, 3.60)
    assert (tc, k) == (pytest.approx(10.0), 1)


def test_no_crossing_returns_nan():
    t = np.array([0.0, 1.0, 2.0])
    v = np.array([3.5, 3.6, 3.7])
    tc, k = crossing_time(t, v, 3.9)
    assert np.isnan(tc) and k == -1


def test_dq_linear_trace_exact():
    # 1 mV/s: 400 mV window lasts 400 s; 740 mA * 400 s = 82.222 mAh
    t, v = linear_trace()
    dq, dur = window_dq(t, v, 3.6, 4.0)
    assert dur == pytest.approx(400.0)
    assert dq == pytest.approx(740.0 * 400.0 / 3600.0)


def test_dq_piecewise_trace():
    # Fast below 3.7 V (2 mV/s), slow above (0.5 mV/s): 50 s + 600 s
    t = np.arange(0.0, 2000.0, 1.0)
    v = np.where(t <= 350, 3.0 + 0.002 * t, 3.7 + 0.0005 * (t - 350))
    dq, dur = window_dq(t, v, 3.6, 4.0)
    assert dur == pytest.approx(50.0 + 600.0)
    assert dq == pytest.approx(740.0 * 650.0 / 3600.0)


def test_dq_uses_given_current():
    t, v = linear_trace()
    dq, _ = window_dq(t, v, 3.6, 4.0, current_ma=370.0)
    assert dq == pytest.approx(370.0 * 400.0 / 3600.0)


def test_dq_independent_of_sample_period():
    a = window_dq(*linear_trace(dt=1.0), 3.6, 4.0)
    b = window_dq(*linear_trace(dt=7.0), 3.6, 4.0)
    assert a[0] == pytest.approx(b[0], rel=1e-9)


def test_window_never_completes():
    t, v = linear_trace(v_end=3.95)
    dq, dur = window_dq(t, v, 3.6, 4.0)
    assert np.isnan(dq) and np.isnan(dur)
