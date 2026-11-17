import warnings

import numpy as np
import pytest

from soh.freeze import gpr_header_text, gpr_params, gpr_predict
from soh.models import gpr
from soh.validate import Win


@pytest.fixture(scope="module")
def fitted():
    rng = np.random.default_rng(3)
    x = rng.uniform([40.0, 60.0], [80.0, 120.0], (50, 2))
    y = 100.0 + 2.0 * x[:, 0] + 1.5 * x[:, 1] + 0.03 * (x[:, 0] - 60.0) ** 2 + rng.normal(0.0, 0.5, 50)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return gpr(2)().fit(x, y), rng.uniform([40.0, 60.0], [80.0, 120.0], (30, 2))


def test_exported_parameters_reproduce_sklearn_mean(fitted):
    est, xq = fitted
    p = gpr_params(Win(3.6, 4.0), est)
    np.testing.assert_allclose(gpr_predict(p, xq), est.predict(xq), rtol=0, atol=1e-6)


def test_gpr_header_round_trips(fitted):
    est, _ = fitted
    p = gpr_params(Win(3.6, 4.0), est)
    text = gpr_header_text(p)
    assert "#define SOH_M6_V1_MV 3600.0" in text and "#define SOH_M6_V2_MV 4000.0" in text
    assert f"#define SOH_M6_N_TRAIN {len(p.alpha)}" in text
    body = text.split("soh_m6_alpha[SOH_M6_N_TRAIN] = {")[1].split("};")[0]
    np.testing.assert_array_equal([float(x) for x in body.replace(",", " ").split()], p.alpha)
