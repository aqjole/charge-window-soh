"""Capacity models. Inputs are window features; target is capacity in mAh."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sklearn.dummy import DummyRegressor
from sklearn.linear_model import LinearRegression

IC_COLS = ("ic_peak_h", "ic_peak_v")


@dataclass(frozen=True)
class Spec:
    cols: tuple[str, ...]
    factory: Callable
    needs_ic: bool = False  # no estimate when IC features are missing (no fallback)


MODELS = {
    "M0": Spec((), lambda: DummyRegressor(strategy="mean")),
    "M1": Spec(("dq",), LinearRegression),
    "M2": Spec(("dq", *IC_COLS), LinearRegression, needs_ic=True),
}

# (IC model, its no-IC control) for paired comparisons
PAIRS = (("M2", "M1"),)
