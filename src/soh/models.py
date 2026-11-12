"""Capacity models. Inputs are window features; target is capacity in mAh."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sklearn.dummy import DummyRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

IC_COLS = ("ic_peak_h", "ic_peak_v")
GPR_RESTARTS = 2
GPR_SEED = 0


@dataclass(frozen=True)
class Spec:
    cols: tuple[str, ...]
    factory: Callable
    needs_ic: bool = False  # no estimate when IC features are missing (no fallback)
    has_std: bool = False  # predict(X, return_std=True) gives a predictive std [mAh]


def gpr(n_features: int) -> Callable:
    """Constant x Matern 5/2 (one length scale per input) + White, on standardized inputs.

    `normalize_y=True`, fixed optimizer restarts and seed. The predictive std includes
    the fitted white-noise term, so intervals are for the measured capacity.
    """

    def make():
        ls = 1.0 if n_features == 1 else [1.0] * n_features
        kernel = ConstantKernel() * Matern(length_scale=ls, nu=2.5) + WhiteKernel()
        return make_pipeline(
            StandardScaler(),
            GaussianProcessRegressor(
                kernel, normalize_y=True, n_restarts_optimizer=GPR_RESTARTS, random_state=GPR_SEED
            ),
        )

    return make


MODELS = {
    "M0": Spec((), lambda: DummyRegressor(strategy="mean")),
    "M1": Spec(("dq",), LinearRegression),
    "M2": Spec(("dq", *IC_COLS), LinearRegression, needs_ic=True),
    "M3": Spec(("dq",), gpr(1), has_std=True),
    "M4": Spec(("dq", *IC_COLS), gpr(3), needs_ic=True, has_std=True),
}

# (IC model, its no-IC control) for paired comparisons
PAIRS = (("M2", "M1"), ("M4", "M3"))
