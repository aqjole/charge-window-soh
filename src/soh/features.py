"""Window features from a charge curve seen as (t_s, v) only.

Current is assumed constant at the nominal 1C value, exactly as the C estimator
does. Every trace either yields a window or a reason code; nothing is dropped.

Crossing detector (same rules as the C estimator):
- Armed at the first sample with v < V1 - ARM_BAND_V.
- t1: first upward V1 crossing after arming. t2: first upward V2 crossing at or
  after the V1 crossing sample. A crossing of level L is the first sample pair
  (k-1, k) with v[k-1] < L <= v[k]; its time is linearly interpolated.
- Later dips below V1 (noise, repeated voltages) do not restart the window.
- GAP if any two consecutive samples from the V1 bracket to the V2 bracket are
  more than MAX_GAP_S apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from soh import NOMINAL_CURRENT_MA

ARM_BAND_V = 0.010
MAX_GAP_S = 120.0


class Reason(str, Enum):
    OK = "OK"
    NOT_ARMED = "NOT_ARMED"  # no sample below V1 - ARM_BAND_V
    NO_V2 = "NO_V2"  # window never completes (V1 or V2 never crossed after arming)
    GAP = "GAP"  # sample gap above MAX_GAP_S inside the window


NO_ESTIMATE_REASONS = [r for r in Reason if r is not Reason.OK]


@dataclass(frozen=True)
class Window:
    reason: Reason
    dq: float = float("nan")  # mAh
    duration_s: float = float("nan")
    t1: float = float("nan")
    t2: float = float("nan")
    k1: int = -1  # sample index that completes the V1 crossing
    k2: int = -1  # sample index that completes the V2 crossing

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


def detect_window(
    t: np.ndarray,
    v: np.ndarray,
    v1: float,
    v2: float,
    current_ma: float = NOMINAL_CURRENT_MA,
    arm_band_v: float = ARM_BAND_V,
    max_gap_s: float = MAX_GAP_S,
) -> Window:
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
