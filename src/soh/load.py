"""Load the Oxford dataset, run the audit gates, and build per-curve records.

Each record pairs one C1ch charge curve (input, as time and voltage) with the
capacity of the C1dc discharge from the same characterization (label).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import scipy.io as sio

from soh import NOMINAL_CURRENT_MA

ROOT = Path(__file__).resolve().parents[2]
MAT_PATH = ROOT / "data" / "raw" / "Oxford_Battery_Degradation_Dataset_1.mat"
MAT_SHA256 = "a8f0b928f4ea77d7ba98b97194b78cc77336f2338fee8b57573d043f0cf26781"

N_CELLS = 8
SECONDS_PER_DAY = 86400.0
CC_TOLERANCE = 0.005  # gate 2: charge current within 0.5 % of nominal
CC_MAX_RESIDUAL_MAH = 1.0  # gate 2: q stays on a straight line in t


class AuditError(RuntimeError):
    """The data contradicts the spec. Stop and ask before changing the method."""


@dataclass(frozen=True)
class Curve:
    cell: int
    cycle: int
    t: np.ndarray  # s from start of the charge
    v: np.ndarray  # V
    capacity_mah: float  # |Δq| of the paired C1dc discharge
    c0_mah: float  # the cell's first valid capacity

    @property
    def soh(self) -> float:
        return self.capacity_mah / self.c0_mah


@dataclass
class Audit:
    sha256: str
    counts: dict[int, int] = field(default_factory=dict)
    excluded: list[tuple[int, int, str]] = field(default_factory=list)
    time_unit: str = ""
    sample_period_s: float = float("nan")
    current_ma: tuple[float, float, float] = (float("nan"),) * 3
    max_cc_residual_mah: float = float("nan")
    cutoff_v: tuple[float, float] = (float("nan"),) * 2

    def to_markdown(self) -> str:
        lo, med, hi = self.current_ma
        lines = [
            "# Data audit",
            "",
            f"- File SHA-256: `{self.sha256}`",
            f"- Time unit of `t`: {self.time_unit}",
            f"- Native sample period (median): {self.sample_period_s:.3f} s",
            f"- C1ch current from q(t) fit: min {lo:.2f}, median {med:.2f}, max {hi:.2f} mA "
            f"(nominal {NOMINAL_CURRENT_MA:.0f} mA, tolerance {100 * CC_TOLERANCE:.1f} %)",
            f"- Max deviation of q from a straight line: {self.max_cc_residual_mah:.3f} mAh",
            f"- Charge cutoff (max v per curve): {self.cutoff_v[0]:.4f} to {self.cutoff_v[1]:.4f} V",
            f"- Valid curves: {sum(self.counts.values())}",
            "",
            "| Cell | Curves |",
            "|---:|---:|",
            *[f"| {c} | {n} |" for c, n in sorted(self.counts.items())],
            "",
            f"Excluded curves: {len(self.excluded)}",
            *[f"- Cell {c} cycle {y}: {why}" for c, y, why in self.excluded],
        ]
        return "\n".join(lines) + "\n"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _arrays(block) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return tuple(np.atleast_1d(np.asarray(getattr(block, k), dtype=float)) for k in ("t", "v", "q"))


def _invalid_reason(t: np.ndarray, v: np.ndarray, q: np.ndarray) -> str | None:
    if t.size < 2 or not (t.size == v.size == q.size):
        return "empty or mismatched arrays"
    if not (np.isfinite(t).all() and np.isfinite(v).all() and np.isfinite(q).all()):
        return "non-finite values"
    if np.any(np.diff(t) <= 0):
        return "time not strictly increasing"
    if abs(q[-1] - q[0]) <= 0:
        return "zero charge throughput"
    return None


def _to_seconds(t: np.ndarray) -> np.ndarray:
    return (t - t[0]) * SECONDS_PER_DAY


def load(path: Path = MAT_PATH, check_hash: bool = True) -> tuple[list[Curve], Audit]:
    """Return valid curves and the audit. Raises AuditError if a gate fails."""
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; see README for the download link")
    sha = file_sha256(path)
    if check_hash and sha != MAT_SHA256:
        raise AuditError(f"dataset SHA-256 mismatch: {sha}")

    mat = sio.loadmat(path, squeeze_me=True, struct_as_record=False)
    cells = sorted(k for k in mat if k.startswith("Cell"))
    if cells != [f"Cell{i}" for i in range(1, N_CELLS + 1)]:
        raise AuditError(f"unexpected cells: {cells}")

    audit = Audit(sha256=sha)
    raw: list[tuple[int, int, np.ndarray, np.ndarray, np.ndarray, float]] = []
    days_span = []
    for name in cells:
        cell = int(name[4:])
        for cyc_name in mat[name]._fieldnames:
            cycle = int(cyc_name[3:])
            block = getattr(mat[name], cyc_name)
            missing = {"C1ch", "C1dc"} - set(block._fieldnames)
            if missing:
                audit.excluded.append((cell, cycle, f"missing {sorted(missing)}"))
                continue
            ch, dc = _arrays(block.C1ch), _arrays(block.C1dc)
            reason = _invalid_reason(*ch) or _invalid_reason(*dc)
            if reason:
                audit.excluded.append((cell, cycle, reason))
                continue
            t, v, q = ch
            days_span.append(t[-1] - t[0])
            raw.append((cell, cycle, t, v, q, abs(dc[2][-1] - dc[2][0])))

    # Gate 1: time unit. A ~1 h charge spans ~0.04 if t is a MATLAB datenum.
    span = float(np.median(days_span))
    if not 0.01 < span < 0.2:
        raise AuditError(f"median C1ch span {span:.4g} in raw t units; not a datenum in days")
    audit.time_unit = "MATLAB datenum (days), converted to seconds from curve start"

    # Gate 2: constant current, and gate 4: sample period. Cutoff recorded.
    currents, residuals, periods, vmax = [], [], [], []
    for _, _, t, v, q, _ in raw:
        ts = _to_seconds(t)
        p = np.polyfit(ts, q, 1)
        currents.append(p[0] * 3600.0)
        residuals.append(np.abs(q - np.polyval(p, ts)).max())
        periods.append(np.median(np.diff(ts)))
        vmax.append(v.max())
    currents = np.array(currents)
    audit.current_ma = (currents.min(), float(np.median(currents)), currents.max())
    audit.max_cc_residual_mah = float(max(residuals))
    audit.sample_period_s = float(np.median(periods))
    audit.cutoff_v = (float(min(vmax)), float(max(vmax)))
    if np.abs(currents / NOMINAL_CURRENT_MA - 1).max() > CC_TOLERANCE:
        raise AuditError(f"C1ch current outside tolerance: {audit.current_ma}")
    if audit.max_cc_residual_mah > CC_MAX_RESIDUAL_MAH:
        raise AuditError(f"C1ch not constant current: residual {audit.max_cc_residual_mah:.3f} mAh")

    # Gate 3: counts. Gate 5: first label of every cell is 1.0 (by construction, checked).
    curves: list[Curve] = []
    for cell in range(1, N_CELLS + 1):
        rows = sorted((r for r in raw if r[0] == cell), key=lambda r: r[1])
        if not rows:
            raise AuditError(f"cell {cell} has no valid curves")
        c0 = rows[0][5]
        for _, cycle, t, v, _, cap in rows:
            curves.append(Curve(cell, cycle, _to_seconds(t), v, cap, c0))
        audit.counts[cell] = len(rows)
        first = next(c for c in curves if c.cell == cell)
        if first.soh != 1.0:
            raise AuditError(f"cell {cell} first label {first.soh} != 1.0")
    return curves, audit


def main() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from soh.report import RESULTS, save_fig

    curves, audit = load()
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "audit.md").write_text(audit.to_markdown())
    print(audit.to_markdown())

    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    for cell in range(1, N_CELLS + 1):
        cs = [c for c in curves if c.cell == cell]
        ax.plot([c.cycle for c in cs], [100 * c.soh for c in cs], marker=".", lw=1, label=f"Cell {cell}")
    ax.set_xlabel("Cycle")
    ax.set_ylabel("SOH [%] (C1dc capacity / first)")
    ax.set_title("Capacity fade, Oxford dataset 1, 40 °C")
    ax.grid(alpha=0.3)
    ax.legend(ncol=2, fontsize=8)
    save_fig(fig, "capacity_fade.png")


if __name__ == "__main__":
    main()
