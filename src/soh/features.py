"""Window features from a charge curve seen as (t_s, v) only.

Commit 1 (MVP): simple upward crossing, time-based dq. Current is assumed
constant at the nominal 1C value, exactly as the C estimator will do.
"""

from __future__ import annotations

import numpy as np

from soh import NOMINAL_CURRENT_MA


def crossing_time(t: np.ndarray, v: np.ndarray, level: float, start: int = 0) -> tuple[float, int]:
    """First upward crossing of `level` at or after sample index `start`.

    The crossing is the first pair (k-1, k) with v[k-1] < level <= v[k]; its time
    is linearly interpolated. Returns (time, k), or (nan, -1) if none.
    """
    below = v[max(start, 1) - 1 : -1] < level
    at_or_above = v[max(start, 1) :] >= level
    hits = np.flatnonzero(below & at_or_above)
    if hits.size == 0:
        return float("nan"), -1
    k = int(hits[0]) + max(start, 1)
    t0, t1, v0, v1 = t[k - 1], t[k], v[k - 1], v[k]
    return float(t0 + (level - v0) * (t1 - t0) / (v1 - v0)), k


def window_dq(
    t: np.ndarray, v: np.ndarray, v1: float, v2: float, current_ma: float = NOMINAL_CURRENT_MA
) -> tuple[float, float]:
    """Charge [mAh] and duration [s] between the V1 and V2 crossings, or (nan, nan)."""
    t1, k1 = crossing_time(t, v, v1)
    if k1 < 0:
        return float("nan"), float("nan")
    t2, k2 = crossing_time(t, v, v2, start=k1)
    if k2 < 0:
        return float("nan"), float("nan")
    duration = t2 - t1
    return current_ma * duration / 3600.0, duration
