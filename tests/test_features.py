import numpy as np
import pytest

from soh.features import (
    ARM_BAND_V,
    END_BAND_V,
    MAX_GAP_S,
    Reason,
    crossing_time,
    detect_first_crossing,
    detect_window,
)

V1, V2 = 3.6, 4.0
I_MA = 740.0


def linear_trace(v_start=3.0, v_end=4.2, rate_v_per_s=0.001, dt=1.0):
    t = np.arange(0.0, (v_end - v_start) / rate_v_per_s + dt, dt)
    return t, v_start + rate_v_per_s * t


def mah(seconds, current_ma=I_MA):
    return current_ma * seconds / 3600.0


# --- crossing primitive ---------------------------------------------------------


def test_crossing_interpolates_between_samples():
    tc, k = crossing_time(np.array([0.0, 10.0, 20.0]), np.array([3.50, 3.60, 3.70]), 3.65)
    assert (tc, k) == (pytest.approx(15.0), 2)


def test_crossing_on_exact_sample():
    tc, k = crossing_time(np.array([0.0, 10.0, 20.0]), np.array([3.50, 3.60, 3.70]), 3.60)
    assert (tc, k) == (pytest.approx(10.0), 1)


def test_no_crossing_returns_nan():
    tc, k = crossing_time(np.array([0.0, 1.0, 2.0]), np.array([3.5, 3.6, 3.7]), 3.9)
    assert np.isnan(tc) and k == -1


# --- clean traces -----------------------------------------------------------------


def test_linear_trace_exact():
    w = detect_window(*linear_trace(), V1, V2)  # 1 mV/s -> 400 s
    assert w.reason is Reason.OK
    assert w.duration_s == pytest.approx(400.0)
    assert w.dq == pytest.approx(mah(400.0))


def test_piecewise_trace():
    # 2 mV/s below 3.7 V, 0.5 mV/s above: 50 s + 600 s
    t = np.arange(0.0, 2000.0, 1.0)
    v = np.where(t <= 350, 3.0 + 0.002 * t, 3.7 + 0.0005 * (t - 350))
    w = detect_window(t, v, V1, V2)
    assert w.duration_s == pytest.approx(650.0)
    assert w.dq == pytest.approx(mah(650.0))


def test_uses_given_current():
    w = detect_window(*linear_trace(), V1, V2, current_ma=370.0)
    assert w.dq == pytest.approx(mah(400.0, 370.0))


def test_independent_of_sample_period_on_linear_trace():
    a = detect_window(*linear_trace(dt=1.0), V1, V2)
    b = detect_window(*linear_trace(dt=7.0), V1, V2)
    assert a.dq == pytest.approx(b.dq, rel=1e-9)


def test_single_sample_jumps_over_both_levels():
    t = np.array([0.0, 10.0, 20.0])
    v = np.array([3.0, 3.5, 4.5])  # 3.6 at t=11, 4.0 at t=15
    w = detect_window(t, v, V1, V2)
    assert w.reason is Reason.OK
    assert (w.t1, w.t2) == (pytest.approx(11.0), pytest.approx(15.0))


# --- edge rule: arming / hysteresis -------------------------------------------------


def test_not_armed_when_trace_starts_at_v1():
    assert detect_window(*linear_trace(v_start=V1), V1, V2).reason is Reason.NOT_ARMED


def test_not_armed_inside_band():
    t, v = linear_trace(v_start=V1 - 0.5 * ARM_BAND_V)
    assert detect_window(t, v, V1, V2).reason is Reason.NOT_ARMED


def test_armed_just_below_band():
    t, v = linear_trace(v_start=V1 - ARM_BAND_V - 0.001)
    assert detect_window(t, v, V1, V2).reason is Reason.OK


def test_arms_on_later_dip():
    # Starts inside the band, dips below it (e.g. relaxation), then charges.
    t = np.arange(0.0, 600.0, 1.0)
    v = np.concatenate([np.full(50, 3.595), np.full(50, 3.585), 3.585 + 0.001 * np.arange(1, 501)])
    w = detect_window(t, v, V1, V2)
    assert w.reason is Reason.OK
    assert w.t1 == pytest.approx(100 + 14, abs=1e-6)  # 3.585 + 0.015


def test_repeated_crossings_average_instead_of_first_winning():
    # Crosses V1 at 1.5, dips back below at ~2.09, re-crosses at ~3.05.
    # t1 = time spent below V1 = 1 + 0.5 + 0.001/0.011 + 0.001/0.021.
    t = np.arange(0.0, 9.0, 1.0)
    v = np.array([3.58, 3.59, 3.61, 3.599, 3.62, 3.8, 3.95, 4.05, 4.1])
    w = detect_window(t, v, V1, V2)
    assert w.t1 == pytest.approx(1 + 0.5 + 0.001 / 0.011 + 0.001 / 0.021)
    assert detect_first_crossing(t, v, V1, V2).t1 == pytest.approx(1.5)  # the old rule


def test_equals_first_crossing_on_monotone_traces():
    for dt in (1.0, 7.0, 60.0):
        t, v = linear_trace(dt=dt)
        a, b = detect_window(t, v, V1, V2), detect_first_crossing(t, v, V1, V2)
        assert (a.t1, a.t2) == (pytest.approx(b.t1), pytest.approx(b.t2))
    t = np.arange(0.0, 2000.0, 1.0)
    v = np.where(t <= 350, 3.0 + 0.002 * t, 3.7 + 0.0005 * (t - 350))
    a, b = detect_window(t, v, V1, V2), detect_first_crossing(t, v, V1, V2)
    assert a.dq == pytest.approx(b.dq)


def test_noise_does_not_bias_the_window():
    # 0.1 mV/s, like the flat part of the charge curve; 5 mV noise.
    rng = np.random.default_rng(0)
    t = np.arange(0.0, 6000.0)
    v = 3.5 + 1e-4 * t
    new, old = [], []
    for _ in range(50):
        vn = v + rng.normal(0, 0.005, len(v))
        new.append(detect_window(t, vn, 3.8, 4.0).t1 - 3000.0)
        old.append(detect_first_crossing(t, vn, 3.8, 4.0).t1 - 3000.0)
    assert abs(np.mean(new)) < 3.0  # seconds
    assert np.mean(old) < -60.0  # the first-crossing rule fires early


def test_no_v2_until_end_band_is_reached():
    t, v = linear_trace(v_end=V2 + END_BAND_V - 0.002)
    assert detect_window(t, v, V1, V2).reason is Reason.NO_V2
    t, v = linear_trace(v_end=V2 + END_BAND_V + 0.002)
    assert detect_window(t, v, V1, V2).reason is Reason.OK


def test_repeated_voltage_samples_at_level():
    t = np.arange(0.0, 10.0, 1.0)
    v = np.array([3.58, 3.59, 3.60, 3.60, 3.60, 3.70, 3.80, 3.90, 4.00, 4.10])
    w = detect_window(t, v, V1, V2)
    assert (w.t1, w.t2) == (pytest.approx(2.0), pytest.approx(8.0))


def test_v2_dip_before_crossing_is_ignored():
    # Voltage plateaus just below V2 with repeated values; first V2 crossing is used.
    t = np.arange(0.0, 8.0, 1.0)
    v = np.array([3.5, 3.7, 3.9, 3.999, 3.999, 3.998, 4.0, 4.1])
    assert detect_window(t, v, V1, V2).t2 == pytest.approx(6.0)


# --- edge rule: window never completes ----------------------------------------------


def test_no_v2_when_charge_stops_inside_window():
    assert detect_window(*linear_trace(v_end=3.95), V1, V2).reason is Reason.NO_V2


def test_no_v2_when_v1_never_reached():
    assert detect_window(*linear_trace(v_end=3.55), V1, V2).reason is Reason.NO_V2


def test_no_estimate_carries_nan_features():
    w = detect_window(*linear_trace(v_end=3.95), V1, V2)
    assert np.isnan(w.dq) and np.isnan(w.duration_s) and not w.ok


# --- edge rule: sample gap -------------------------------------------------------------


def gapped_trace(gap_start_s, gap_s):
    t, v = linear_trace()
    keep = (t <= gap_start_s) | (t >= gap_start_s + gap_s)
    return t[keep], v[keep]


def test_gap_inside_window():
    # V1 at t=600, V2 at t=1000
    assert detect_window(*gapped_trace(700, MAX_GAP_S + 1), V1, V2).reason is Reason.GAP


def test_gap_at_limit_is_allowed():
    assert detect_window(*gapped_trace(700, MAX_GAP_S), V1, V2).reason is Reason.OK


def test_gap_across_v1_crossing():
    assert detect_window(*gapped_trace(550, MAX_GAP_S + 1), V1, V2).reason is Reason.GAP


def test_gap_across_v2_crossing():
    assert detect_window(*gapped_trace(950, MAX_GAP_S + 1), V1, V2).reason is Reason.GAP


def test_gap_outside_window_is_ignored():
    assert detect_window(*gapped_trace(100, 300), V1, V2).reason is Reason.OK  # before V1
    assert detect_window(*gapped_trace(1040, 150), V1, V2).reason is Reason.OK  # after V2 + end band


def test_gap_between_v2_and_end_band_is_ignored():
    # V2 at t=1000, V2 + END_BAND_V at t=1030: no window time accrues above V2.
    assert detect_window(*gapped_trace(1001, MAX_GAP_S + 20), V1, V2).reason is Reason.OK


# --- IC features -------------------------------------------------------------------------

from soh.features import IC_BIN_V, ic_features  # noqa: E402


def ic_trace(v_peak=3.9, width_v=0.02, q_step=200.0, slope=300.0, v_start=3.5, v_end=4.2, dv=0.0005):
    """Trace with q(V) = slope*(V - v_start) + q_step * logistic((V - v_peak)/width): known IC peak."""
    v = np.arange(v_start, v_end, dv)
    q = slope * (v - v_start) + q_step / (1 + np.exp(-(v - v_peak) / width_v))
    t = q * 3600 / I_MA
    peak_h = slope + q_step / (4 * width_v)
    return t, v, peak_h


def ic_of(t, v, v1, v2):
    return ic_features(t, v, detect_window(t, v, v1, v2), v1, v2)


def test_ic_finds_known_peak():
    t, v, peak_h = ic_trace()
    ic = ic_of(t, v, 3.8, 4.0)
    assert ic.reason is Reason.OK
    assert abs(ic.peak_v - 3.9) <= IC_BIN_V
    assert ic.peak_h == pytest.approx(peak_h, rel=0.05)


def test_ic_peak_moves_with_true_peak():
    t, v, _ = ic_trace(v_peak=3.85)
    assert abs(ic_of(t, v, 3.7, 4.0).peak_v - 3.85) <= IC_BIN_V


def test_ic_edge_when_peak_outside_window():
    t, v, _ = ic_trace(v_peak=4.05)  # dQ/dV still rising at V2
    assert ic_of(t, v, 3.7, 3.9).reason is Reason.IC_EDGE


def test_ic_edge_when_peak_below_window():
    t, v, _ = ic_trace(v_peak=3.65)  # dQ/dV falling from V1
    assert ic_of(t, v, 3.8, 4.0).reason is Reason.IC_EDGE


def test_ic_sparse_with_few_samples():
    t, v, _ = ic_trace()
    keep = np.arange(0, len(t), 40)  # one sample per 20 mV -> 75 % of 5 mV bins empty
    t, v = t[keep], v[keep]
    w = detect_window(t, v, 3.8, 4.0, max_gap_s=np.inf)  # isolate the sparse-bin rule from GAP
    assert ic_features(t, v, w, 3.8, 4.0).reason is Reason.IC_SPARSE


def test_ic_tolerates_some_empty_bins():
    t, v, _ = ic_trace()
    keep = np.arange(0, len(t), 16)  # one sample per 8 mV -> under half the bins empty
    ic = ic_of(t[keep], v[keep], 3.8, 4.0)
    assert ic.reason is Reason.OK
    assert abs(ic.peak_v - 3.9) <= 2 * IC_BIN_V


def test_ic_inherits_window_reason():
    t, v, _ = ic_trace(v_end=3.95)
    assert ic_of(t, v, 3.8, 4.0).reason is Reason.NO_V2
