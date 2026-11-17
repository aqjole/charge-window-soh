"""Capacity models. Inputs are window features; target is capacity in mAh."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from sklearn.dummy import DummyRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from soh.features import N_SEG

IC_COLS = ("ic_peak_h", "ic_peak_v")
SEGMENT_COLS = ("dq_a", "dq_b")  # dq split at the window midpoint; dq_a + dq_b = dq
CURVE_COLS = tuple(f"s{k}" for k in range(N_SEG))  # charge of each of N_SEG equal-voltage segments
GPR_RESTARTS = 2
GPR_SEED = 0


@dataclass(frozen=True)
class Spec:
    cols: tuple[str, ...]
    factory: Callable
    needs_ic: bool = False  # no estimate when IC features are missing (no fallback)
    has_std: bool = False  # predict(X, return_std=True) gives a predictive std [mAh]
    augment: bool | str = False  # True: also trains on offset copies; "noise": offset + noise copy


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


def gpr_curve() -> Callable:
    """Constant x Matern 5/2 with one shared length scale + White, on the unscaled segment
    charges [mAh]: the kernel compares two windows by the distance between their charge
    curves. `normalize_y=True`, fixed optimizer restarts and seed, as `gpr`."""

    def make():
        kernel = ConstantKernel() * Matern(length_scale=10.0, nu=2.5) + WhiteKernel()
        return GaussianProcessRegressor(kernel, normalize_y=True, n_restarts_optimizer=GPR_RESTARTS, random_state=GPR_SEED)

    return make


class HalvesPlusCurve:
    """M8: a linear model on the window's two halves, plus `gpr_curve` on its residual.

    Inputs are the N_SEG segment charges; the halves are the sums of the first and second
    N_SEG / 2 (= dq_a, dq_b). The linear part carries the noise-robust level and tilt, the
    GPR the finer curve shape. The predictive std is the residual GPR's.
    """

    def _halves(self, X: np.ndarray) -> np.ndarray:
        h = X.shape[1] // 2
        return np.c_[X[:, :h].sum(axis=1), X[:, h:].sum(axis=1)]

    def fit(self, X: np.ndarray, y: np.ndarray) -> HalvesPlusCurve:
        self.lin_ = LinearRegression().fit(self._halves(X), y)
        self.gp_ = gpr_curve()().fit(X, y - self.lin_.predict(self._halves(X)))
        return self

    def predict(self, X: np.ndarray, return_std: bool = False):
        base = self.lin_.predict(self._halves(X))
        if return_std:
            mu, sd = self.gp_.predict(X, return_std=True)
            return base + mu, sd
        return base + self.gp_.predict(X)


MODELS = {
    "M0": Spec((), lambda: DummyRegressor(strategy="mean")),
    "M1": Spec(("dq",), LinearRegression),
    "M2": Spec(("dq", *IC_COLS), LinearRegression, needs_ic=True),
    "M3": Spec(("dq",), gpr(1), has_std=True),
    "M4": Spec(("dq", *IC_COLS), gpr(3), needs_ic=True, has_std=True),
    "M5": Spec(SEGMENT_COLS, gpr(2), has_std=True),
    "M6": Spec(SEGMENT_COLS, gpr(2), has_std=True, augment=True),
    "M8": Spec(CURVE_COLS, HalvesPlusCurve, has_std=True, augment="noise"),
}

# (model, its control, what the model adds) for paired comparisons
PAIRS = (
    ("M2", "M1", "IC peak"),
    ("M4", "M3", "IC peak"),
    ("M5", "M3", "two segments"),
    ("M6", "M5", "offset augmentation"),
    ("M8", "M6", "curve residual and noise copy"),
    ("M8", "M4", "curve instead of IC peak"),
)
