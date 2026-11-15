"""Export the traces the C replay and the agreement check both read.

One CSV per case in `build/traces/`, rows `cell,cycle,c0_mah,t_s,v_mV`, numbers as
`%.9g`. Cases: every clean trace, and seed 0 of the combined degraded case (same
degradation as in `soh.degrade`). The files are derived from the dataset, so they
are build output and not committed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from soh.degrade import CASES, degrade, trace_rng
from soh.load import Curve, load
from soh.report import ROOT

TRACES = ROOT / "build" / "traces"
COLUMNS = ["cell", "cycle", "c0_mah", "t_s", "v_mV"]
COMBINED = next(c for c in CASES if c.name == "combined")
EXPORTS = {"clean": None, "combined_seed0": (COMBINED, 0)}


def trace_frame(c: Curve, t: np.ndarray, v: np.ndarray) -> pd.DataFrame:
    n = len(t)
    return pd.DataFrame(
        dict(cell=np.full(n, c.cell), cycle=np.full(n, c.cycle), c0_mah=np.full(n, c.c0_mah), t_s=t, v_mV=1000.0 * v)
    )


def export(curves: list[Curve], name: str, out_dir: Path = TRACES) -> Path:
    spec = EXPORTS[name]
    parts = []
    for c in curves:
        t, v = (c.t, c.v) if spec is None else degrade(c.t, c.v, spec[0], trace_rng(spec[1], c.cell, c.cycle))
        parts.append(trace_frame(c, t, v))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.csv"
    pd.concat(parts, ignore_index=True)[COLUMNS].to_csv(path, index=False, float_format="%.9g", lineterminator="\n")
    return path


def main() -> None:
    curves, _ = load()
    for name in EXPORTS:
        path = export(curves, name)
        print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
