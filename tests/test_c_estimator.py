"""C estimator vs the Python detector on synthetic traces (no dataset needed).

The replay tool is compiled into a temporary directory with the same flags as the
Makefile; the tests are skipped when no C compiler is available.
"""

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from soh.agree import c_estimates, compare, python_estimates
from soh.export import COLUMNS
from soh.freeze import Frozen, header_text
from soh.report import ROOT
from soh.validate import Win

CC = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
pytestmark = pytest.mark.skipif(CC is None, reason="no C compiler")

WIN = Win(3.6, 4.0)
FROZEN = Frozen(WIN, 12.5, 1.75)
ARGS = ("3600", "4000", "12.5", "1.75")
C0 = 740.0


@pytest.fixture(scope="module")
def replay(tmp_path_factory):
    d = tmp_path_factory.mktemp("c")
    (d / "soh_model.h").write_text(header_text(FROZEN))
    exe = d / "replay"
    cmd = [CC, "-std=c99", "-O2", "-Wall", "-Wextra", "-pedantic", "-Werror", "-ffp-contract=off",
           f"-I{d}", f"-I{ROOT / 'c'}", "-o", str(exe), str(ROOT / "c" / "replay.c"), str(ROOT / "c" / "soh_est.c"), "-lm"]
    subprocess.run(cmd, check=True)
    return exe


def frame(traces: dict[int, tuple[np.ndarray, np.ndarray]]) -> pd.DataFrame:
    parts = [
        pd.DataFrame(dict(cell=1, cycle=k, c0_mah=C0, t_s=t, v_mV=1000.0 * v)) for k, (t, v) in traces.items()
    ]
    return pd.concat(parts, ignore_index=True)[COLUMNS]


def run_both(replay, tmp_path, traces, args=ARGS):
    df = frame(traces)
    path = tmp_path / "traces.csv"
    df.to_csv(path, index=False, float_format="%.9g", lineterminator="\n")
    df = pd.read_csv(path)  # both sides see the same rounded numbers
    py, c = python_estimates(df, FROZEN), c_estimates(path, replay, args)
    return py, c, compare(py, c)


def ramp(v0=3.0, v1=4.2, rate=0.5e-3, dt=1.0):
    t = np.arange(0.0, (v1 - v0) / rate + dt, dt)
    return t, v0 + rate * t


def noisy(seed, sigma_v=0.005, dt=1.0):
    t, v = ramp(dt=dt)
    return t, v + np.random.default_rng(seed).normal(0, sigma_v, len(t))


def test_linear_ramp_exact(replay, tmp_path):
    py, c, r = run_both(replay, tmp_path, {0: ramp()})
    assert r["passed"] and r["n_OK"] == 1
    dq = 740.0 * 800.0 / 3600.0  # 400 mV at 0.5 mV/s
    assert c.dq_mah.iloc[0] == pytest.approx(dq, rel=1e-9)
    assert c.capacity_mah.iloc[0] == pytest.approx(12.5 + 1.75 * dq, rel=1e-9)
    assert c.soh.iloc[0] == pytest.approx((12.5 + 1.75 * dq) / C0, rel=1e-9)


def test_noisy_traces_match_python(replay, tmp_path):
    traces = {k: noisy(k) for k in range(20)}
    py, c, r = run_both(replay, tmp_path, traces)
    assert r["passed"] and r["n_OK"] == 20
    assert r["max_abs_diff_dq_mah"] < 1e-9


def test_quantized_decimated_traces_match_python(replay, tmp_path):
    traces = {}
    for k in range(10):
        t, v = noisy(100 + k, sigma_v=0.002, dt=10.0)
        traces[k] = (t, np.round(v / 0.001) * 0.001)  # 1 mV LSB: samples land exactly on the levels
    py, c, r = run_both(replay, tmp_path, traces)
    assert r["passed"] and r["n_OK"] == 10


def test_reason_codes(replay, tmp_path):
    t, v = ramp()
    gap_in = ~((v > 3.7) & (v < 3.8))  # 200 s hole inside the window
    gap_out = ~((v > 3.2) & (v < 3.4))  # hole below the window
    traces = {
        0: (t, v + 0.7),  # starts above V1 - arm band
        1: (t[v < 3.95], v[v < 3.95]),  # never reaches V2 + end band
        2: (t[gap_in], v[gap_in]),
        3: (t[gap_out], v[gap_out]),
        4: (t[v < 4.025], v[v < 4.025]),  # reaches V2 but not V2 + 30 mV
    }
    py, c, r = run_both(replay, tmp_path, traces)
    assert r["passed"]
    assert list(c.reason) == ["NOT_ARMED", "NO_V2", "GAP", "OK", "NO_V2"]


def test_dip_back_below_level_counts_time_below(replay, tmp_path):
    # rises through V1, falls back below it for a while, then completes
    t = np.arange(0.0, 3000.0, 1.0)
    v = np.interp(t, [0, 600, 900, 1200, 3000], [3.3, 3.65, 3.55, 3.65, 4.2])
    py, c, r = run_both(replay, tmp_path, {0: (t, v)})
    assert r["passed"] and r["n_OK"] == 1


def test_frozen_header_round_trips():
    text = header_text(Frozen(Win(3.8, 4.0), 91.925359066971623, 1.986876473314624))
    defs = [line.split() for line in text.splitlines() if line.startswith("#define SOH_MODEL_")]
    vals = {name: value for _, name, value in (d for d in defs if len(d) == 3)}
    assert float(vals["SOH_MODEL_A_MAH"]) == 91.925359066971623
    assert float(vals["SOH_MODEL_B"]) == 1.986876473314624
    assert float(vals["SOH_MODEL_V1_MV"]) == 3800.0
