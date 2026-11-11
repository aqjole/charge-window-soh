"""Capacity models. Inputs are window features; target is capacity in mAh."""

from __future__ import annotations

from sklearn.dummy import DummyRegressor
from sklearn.linear_model import LinearRegression

# name -> (feature columns, factory)
MODELS = {
    "M0": ((), lambda: DummyRegressor(strategy="mean")),
    "M1": (("dq",), lambda: LinearRegression()),
}
