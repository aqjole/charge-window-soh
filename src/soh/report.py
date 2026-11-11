"""Shared output helpers: results directory, deterministic tables and figures."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
FLOAT_FMT = "%.4f"


def write_table(df: pd.DataFrame, stem: str, title: str, note: str = "") -> None:
    """Write `results/<stem>.csv` and `results/<stem>.md` with fixed float formatting."""
    RESULTS.mkdir(exist_ok=True)
    df.to_csv(RESULTS / f"{stem}.csv", index=False, float_format=FLOAT_FMT, lineterminator="\n")
    md = [f"# {title}", ""]
    if note:
        md += [note, ""]
    md.append(df.to_markdown(index=False, floatfmt=".3f"))
    (RESULTS / f"{stem}.md").write_text("\n".join(md) + "\n")


def save_fig(fig, name: str) -> None:
    import matplotlib.pyplot as plt

    RESULTS.mkdir(exist_ok=True)
    fig.tight_layout()
    fig.savefig(RESULTS / name, dpi=150, metadata={"Software": None})
    plt.close(fig)
