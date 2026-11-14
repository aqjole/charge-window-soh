"""Window features from a charge curve seen as (t_s, v) only.

Current is assumed constant at the nominal 1C value, exactly as the C estimator
does. Every trace either yields a window or a reason code; nothing is dropped.

Window detector, time-below-level (same rules as the C estimator):
- Armed at the first sample with v < V1 - ARM_BAND_V.
- Done at the first later sample with v >= V2 + END_BAND_V.
- Between those two samples the voltage is taken as piecewise linear, and the time
  it spends below V1 and below V2 is accumulated. t1 = t_arm + time below V1,
  t2 = t_arm + time below V2, so the window duration is the time spent between
  the two levels.
- On a monotone trace this equals the first upward crossings, linearly
  interpolated. With noise, repeated crossings of a level average out instead of
  the first one winning, which removes the early bias of a first-crossing rule
  (about sigma / (dV/dt) per level).
- NO_V2 if the trace never reaches V2 + END_BAND_V. GAP if a segment that
  contributes window time is longer than MAX_GAP_S.

`detect_first_crossing` is the rule used up to commit 6. It is kept only as the
baseline in the degraded-log comparison.

IC features (used by M2/M4 only), from the samples with t1 <= t < t2:
- bin samples by voltage into IC_BIN_V bins from V1 to V2; per bin, mean sample
  time since t1 -> q = I * t / 3600 [mAh]; empty bins filled by linear interpolation;
- Savitzky-Golay first derivative (IC_SG_LEN bins, order IC_SG_ORDER) -> dQ/dV [mAh/V];
- ic_peak_h, ic_peak_v = height and bin-centre voltage of the maximum.
These settings were fixed before the first outer run that includes IC.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
from scipy.signal import savgol_filter

from soh import NOMINAL_CURRENT_MA

ARM_BAND_V = 0.010
END_BAND_V = 0.030  # must not exceed the window grid's margin to the charge cutoff
MAX_GAP_S = 120.0

IC_BIN_V = 0.005
IC_SG_LEN = 7
IC_SG_ORDER = 2
IC_MAX_EMPTY = 0.5


class Reason(str, Enum):
    OK = "OK"
    NOT_ARMED = "NOT_ARMED"  # no sample below V1 - ARM_BAND_V
    NO_V2 = "NO_V2"  # window never completes (never reaches V2 + END_BAND_V after arming)
    GAP = "GAP"  # sample gap above MAX_GAP_S inside the window
    IC_SPARSE = "IC_SPARSE"  # more than IC_MAX_EMPTY of the voltage bins have no sample
    IC_EDGE = "IC_EDGE"  # dQ/dV maximum in the first or last bin, or not positive
    NO_TRAIN = "NO_TRAIN"  # model has no answered training traces at this window


NO_ESTIMATE_REASONS = [r for r in Reason if r is not Reason.OK]
WINDOW_REASONS = [Reason.NOT_ARMED, Reason.NO_V2, Reason.GAP]


@dataclass(frozen=True)
class Window:
    reason: Reason
    dq: float = float("nan")  # mAh
    duration_s: float = float("nan")
    t1: float = float("nan")
    t2: float = float("nan")
    k1: int = -1  # first sample index at or after t1
    k2: int = -1  # first sample index at or after t2

    @property
    def ok(self) -> bool:
        return self.reason is Reason.OK


def crossing_time(t: np.ndarray, v: np.ndarray, level: float, start: int = 0) -> tuple[float, int]:
    """First upward crossing of `level` by a pair (k-1, k) with k >= max(start, 1).

    Returns (interpolated time, k), or (nan, -1) if there is none.
    """
    s = max(start, 1)
    hits = np.flatnonzero((v[s - 1 : -1] < level) & (v[s:] >= level))
    if hits.size == 0:
        return float("nan"), -1
    k = int(hits[0]) + s
    t0, t1, v0, v1 = t[k - 1], t[k], v[k - 1], v[k]
    return float(t0 + (level - v0) * (t1 - t0) / (v1 - v0)), k


def time_below(t: np.ndarray, v: np.ndarray, level: float) -> np.ndarray:
    """Per segment (k, k+1): time the linearly interpolated voltage spends below `level`."""
    a, b = v[:-1], v[1:]
    frac = ((a < level) & (b < level)).astype(float)
    up = (a < level) & (b >= level)
    down = (a >= level) & (b < level)
    frac[up] = (level - a[up]) / (b[up] - a[up])
    frac[down] = (level - b[down]) / (a[down] - b[down])
    return frac * np.diff(t)


def detect_window(
    t: np.ndarray,
    v: np.ndarray,
    v1: float,
    v2: float,
    current_ma: float = NOMINAL_CURRENT_MA,
    arm_band_v: float = ARM_BAND_V,
    max_gap_s: float = MAX_GAP_S,
    end_band_v: float = END_BAND_V,
) -> Window:
    """Time-below-level window detector (see module docstring)."""
    armed = np.flatnonzero(v < v1 - arm_band_v)
    if armed.size == 0:
        return Window(Reason.NOT_ARMED)
    s = int(armed[0])
    done = np.flatnonzero(v[s:] >= v2 + end_band_v)
    if done.size == 0:
        return Window(Reason.NO_V2)
    e = s + int(done[0])
    ts, vs = t[s : e + 1], v[s : e + 1]
    below1, below2 = time_below(ts, vs, v1), time_below(ts, vs, v2)
    if (np.diff(ts)[below2 - below1 > 0] > max_gap_s).any():
        return Window(Reason.GAP)
    t1, t2 = float(ts[0] + below1.sum()), float(ts[0] + below2.sum())
    duration = t2 - t1
    eps = 1e-9  # a level met exactly on a sample belongs to the window
    k1, k2 = int(np.searchsorted(t, t1 - eps)), int(np.searchsorted(t, t2 - eps))
    return Window(Reason.OK, current_ma * duration / 3600.0, duration, t1, t2, k1, k2)


def detect_first_crossing(
    t: np.ndarray,
    v: np.ndarray,
    v1: float,
    v2: float,
    current_ma: float = NOMINAL_CURRENT_MA,
    arm_band_v: float = ARM_BAND_V,
    max_gap_s: float = MAX_GAP_S,
) -> Window:
    """Baseline: first upward V1 crossing after arming, then first upward V2 crossing."""
    armed = np.flatnonzero(v < v1 - arm_band_v)
    if armed.size == 0:
        return Window(Reason.NOT_ARMED)
    t1, k1 = crossing_time(t, v, v1, start=int(armed[0]) + 1)
    if k1 < 0:
        return Window(Reason.NO_V2)
    t2, k2 = crossing_time(t, v, v2, start=k1)
    if k2 < 0:
        return Window(Reason.NO_V2)
    if np.diff(t[k1 - 1 : k2 + 1]).max() > max_gap_s:
        return Window(Reason.GAP)
    duration = t2 - t1
    return Window(Reason.OK, current_ma * duration / 3600.0, duration, t1, t2, k1, k2)


@dataclass(frozen=True)
class IC:
    reason: Reason
    peak_h: float = float("nan")  # mAh/V
    peak_v: float = float("nan")  # V


def ic_curve(
    t: np.ndarray, v: np.ndarray, w: Window, v1: float, v2: float, current_ma: float = NOMINAL_CURRENT_MA
) -> tuple[np.ndarray, np.ndarray, float]:
    """Bin centres [V], dQ/dV [mAh/V] and empty-bin fraction for a completed window."""
    n_bins = int(round((v2 - v1) / IC_BIN_V))
    centres = v1 + IC_BIN_V * (np.arange(n_bins) + 0.5)
    vs, ts = v[w.k1 : w.k2], t[w.k1 : w.k2] - w.t1
    idx = np.floor((vs - v1) / IC_BIN_V).astype(int)
    inside = (idx >= 0) & (idx < n_bins)
    counts = np.bincount(idx[inside], minlength=n_bins)
    sums = np.bincount(idx[inside], weights=ts[inside], minlength=n_bins)
    filled = counts > 0
    empty_frac = 1.0 - filled.mean()
    if filled.sum() < 2:
        return centres, np.full(n_bins, np.nan), empty_frac
    t_bin = np.interp(centres, centres[filled], sums[filled] / counts[filled])
    q = current_ma * t_bin / 3600.0
    dqdv = savgol_filter(q, IC_SG_LEN, IC_SG_ORDER, deriv=1, delta=IC_BIN_V)
    return centres, dqdv, empty_frac


def ic_features(
    t: np.ndarray, v: np.ndarray, w: Window, v1: float, v2: float, current_ma: float = NOMINAL_CURRENT_MA
) -> IC:
    """IC peak of a window. Inherits the window reason when the window failed."""
    if not w.ok:
        return IC(w.reason)
    centres, dqdv, empty_frac = ic_curve(t, v, w, v1, v2, current_ma)
    if empty_frac > IC_MAX_EMPTY:
        return IC(Reason.IC_SPARSE)
    k = int(np.argmax(dqdv))
    if k == 0 or k == len(dqdv) - 1 or not dqdv[k] > 0:
        return IC(Reason.IC_EDGE)
    return IC(Reason.OK, float(dqdv[k]), float(centres[k]))
