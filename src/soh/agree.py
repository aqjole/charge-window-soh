"""Agreement between the C estimator and the Python reference, for M1 and M6.

Both read the same exported CSV (`soh.export`). The Python side runs
`detect_window` on each trace at the frozen window and applies the frozen model:
M1's coefficients, or M6's fitted sklearn GPR (pickled by `soh.freeze`). The C
side is `build/replay` (`replay m6` for M6). Gate: identical reason codes on every
trace and |SOH_C - SOH_Python| <= 1e-4 on every answered trace, for all clean
traces and seed 0 of the combined degraded case. Exits non-zero on failure.
"""

from __future__ import annotations

import math
import subprocess
import sys
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd

from soh.export import EXPORTS, TRACES
from soh.features import Reason, detect_window
from soh.freeze import Frozen, load_frozen, load_frozen_gpr
from soh.report import ROOT, write_table

REPLAY = ROOT / "build" / "replay"
TOL_SOH = 1e-4
KEY = ["cell", "cycle"]


def estimates(traces: pd.DataFrame, win, capacity) -> pd.DataFrame:
    """Per trace: window reason, dq and `capacity(window)` [mAh] with its SOH."""
    rows = []
    for (cell, cycle), g in traces.groupby(KEY, sort=False):
        w = detect_window(g.t_s.to_numpy(), g.v_mV.to_numpy() / 1000.0, win.v1, win.v2)
        row = dict(cell=cell, cycle=cycle, reason=w.reason.value, dq_mah=np.nan, capacity_mah=np.nan, soh=np.nan)
        if w.ok:
            cap = capacity(w)
            row.update(dq_mah=w.dq, capacity_mah=cap, soh=cap / g.c0_mah.iloc[0])
        rows.append(row)
    return pd.DataFrame(rows)


def python_estimates(traces: pd.DataFrame, f: Frozen) -> pd.DataFrame:
    """M1 reference: frozen coefficients on dq."""
    return estimates(traces, f.win, lambda w: f.a_mah + f.b * w.dq)


def python_estimates_gpr(traces: pd.DataFrame, win, est) -> pd.DataFrame:
    """M6 reference: the fitted sklearn GPR's mean on (dq_a, dq_b)."""
    return estimates(traces, win, lambda w: float(est.predict(np.array([[w.dq_a, w.dq_b]]))[0]))


def c_estimates(path: Path, replay: Path = REPLAY, args: tuple[str, ...] = ()) -> pd.DataFrame:
    with path.open() as fh:
        out = subprocess.run([str(replay), *args], stdin=fh, capture_output=True, text=True, check=True).stdout
    return pd.read_csv(StringIO(out))


def compare(py: pd.DataFrame, c: pd.DataFrame) -> dict:
    m = py.merge(c, on=KEY, how="outer", suffixes=("_py", "_c"), indicator=True)
    missing = int((m["_merge"] != "both").sum())
    mismatch = int((m.reason_py != m.reason_c).sum())
    ok = m[(m.reason_py == Reason.OK.value) & (m.reason_c == Reason.OK.value)]
    d_soh = float((ok.soh_py - ok.soh_c).abs().max()) if len(ok) else 0.0
    d_dq = float((ok.dq_mah_py - ok.dq_mah_c).abs().max()) if len(ok) else 0.0
    counts = {f"n_{r.value}": int((m.reason_py == r.value).sum()) for r in (Reason.OK, Reason.NOT_ARMED, Reason.NO_V2, Reason.GAP)}
    return dict(
        n_traces=len(m), **counts, missing_traces=missing, reason_mismatches=mismatch,
        max_abs_diff_soh=d_soh, max_abs_diff_dq_mah=d_dq,
        passed=missing == 0 and mismatch == 0 and d_soh <= TOL_SOH,
    )


def bound(x: float) -> str:
    """Power-of-ten upper bound, stable across machines where the exact last bits are not."""
    return "0" if x == 0 else f"< 1e{math.floor(math.log10(x)) + 1}"


def main() -> None:
    if not REPLAY.exists():
        sys.exit(f"{REPLAY.relative_to(ROOT)} not found; run `make c`")
    f = load_frozen()
    win6, est6 = load_frozen_gpr()
    rows = []
    for name in EXPORTS:
        path = TRACES / f"{name}.csv"
        traces = pd.read_csv(path)
        for model, py, args in (
            ("M1", python_estimates(traces, f), ()),
            ("M6", python_estimates_gpr(traces, win6, est6), ("m6",)),
        ):
            r = compare(py, c_estimates(path, args=args))
            print(f"{model} {name}: {r}")
            rows.append(dict(model=model, case=name, **r))
    df = pd.DataFrame(rows)
    all_passed = bool(df.passed.all())
    for col in ("max_abs_diff_soh", "max_abs_diff_dq_mah"):
        df[col] = df[col].map(bound)
    df["passed"] = df.passed.map({True: "yes", False: "no"})
    note = (
        f"C estimator (`c/soh_est.c`, via `build/replay`) against the Python reference on the same exported "
        f"CSV (`%.9g`): frozen M1 at {f.win} V against its coefficients, frozen M6 at {win6} V against the "
        "fitted sklearn GPR. Gate: identical reason codes on every trace and "
        f"|SOH difference| <= {TOL_SOH:g} on every answered trace. Differences are shown as a power-of-ten "
        "upper bound; SOH is a fraction (1e-4 = 0.01 SOH points)."
    )
    write_table(df, "c_agreement", "C estimator agreement", note)
    if not all_passed:
        sys.exit("C and Python estimates disagree")


if __name__ == "__main__":
    main()
