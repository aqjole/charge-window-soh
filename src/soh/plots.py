"""Figures written to results/."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from soh import NOMINAL_CURRENT_MA  # noqa: E402
from soh.features import detect_window, ic_curve  # noqa: E402
from soh.load import Curve  # noqa: E402
from soh.report import save_fig  # noqa: E402

WINDOW_COLORS = {"M1": "C0", "M2": "C1"}
Z95 = 1.959964  # same constant as validate.Z95; not imported to avoid a cycle


def frontier(pooled: pd.DataFrame, cells: pd.DataFrame, model: str = "M1") -> None:
    """Held-out RMSE vs median window duration for each width regime and for `any`."""
    p = pooled[pooled.model == model].set_index("regime")
    c = cells[cells.model == model].groupby("regime").rmse.agg(["min", "max"])
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    for regime in p.index:
        x, y = p.loc[regime, "median_window_s"] / 60, p.loc[regime, "rmse"]
        lo, hi = y - c.loc[regime, "min"], c.loc[regime, "max"] - y
        fixed = regime != "any"
        ax.errorbar(
            x, y, yerr=[[lo], [hi]], fmt="o" if fixed else "D", ms=7, capsize=4,
            color="C0" if fixed else "C3", label=None if fixed else "any width (selected per fold)",
        )
        text = f"{regime[1:]} mV\n{p.loc[regime, 'windows'].split(' x')[0]} V" if fixed else "any"
        ax.annotate(text, (x, y + hi), xytext=(0, 5), textcoords="offset points", fontsize=8, ha="center", va="bottom")
    ax.plot([], [], "o", color="C0", label="one width only")
    ax.set_xlabel("Median window duration at 1C [min]")
    ax.set_ylabel("Held-out RMSE [SOH points]")
    ax.set_title(f"{model}: accuracy vs window width (nested leave-one-cell-out)\nbars: best to worst held-out cell")
    ax.set_ylim(0, c["max"].max() + 0.35)
    ax.set_xlim(ax.get_xlim()[0] - 1, ax.get_xlim()[1] + 1)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="upper right")
    save_fig(fig, "accuracy_vs_window.png")


def charge_curves(curves: list[Curve], windows: dict, cell: int = 1, every: int = 2000) -> None:
    """Charge curves and dQ/dV of one cell over life, with each model's most-selected window."""
    cs = [c for c in curves if c.cell == cell]
    targets = range(0, max(c.cycle for c in cs) + 1, every)
    picked = [min(cs, key=lambda c: abs(c.cycle - t)) for t in targets]
    cmap = plt.get_cmap("viridis")
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 4.0))
    for i, c in enumerate(picked):
        color = cmap(i / max(len(picked) - 1, 1))
        label = f"cycle {c.cycle}, SOH {100 * c.soh:.0f} %"
        a.plot(NOMINAL_CURRENT_MA * c.t / 3600, c.v, color=color, lw=1.2, label=label)
        lo, hi = 3.45, 4.15
        w = detect_window(c.t, c.v, lo, hi)
        if w.ok:
            x, y, _ = ic_curve(c.t, c.v, w, lo, hi)
            b.plot(x, y, color=color, lw=1.2, label=label)
    for i, (name, win) in enumerate(windows.items()):
        col = WINDOW_COLORS.get(name, "C3")
        # first window filled, later ones dashed outlines, so overlaps stay readable
        style = dict(color=col, alpha=0.15) if i == 0 else dict(fill=False, edgecolor=col, ls="--", lw=1.5)
        a.axhspan(win.v1, win.v2, **style, label=f"{name} window {win.v1:.1f}-{win.v2:.1f} V")
        b.axvspan(win.v1, win.v2, **style, label=f"{name} window {win.v1:.1f}-{win.v2:.1f} V")
    a.set_xlabel("Charge since start of 1C charge [mAh]")
    a.set_ylabel("Voltage [V]")
    a.set_title(f"Cell {cell}: 1C charge curves")
    a.grid(alpha=0.3)
    a.legend(fontsize=7, loc="lower right")
    b.set_xlabel("Voltage [V]")
    b.set_ylabel("dQ/dV [mAh/V]")
    b.set_title("Incremental capacity (5 mV bins, Savitzky-Golay 7/2)")
    b.set_ylim(bottom=0)
    b.grid(alpha=0.3)
    handles, labels = b.get_legend_handles_labels()
    b.legend(handles[-len(windows):], labels[-len(windows):], fontsize=7, loc="upper left")
    fig.suptitle("Most-selected window per model (any-width regime)")
    save_fig(fig, "charge_curves_window.png")



def predictions(preds: dict[str, pd.DataFrame], regime: str = "any") -> None:
    """Held-out error per cell with each probabilistic model's 95 % predictive band.

    The band covers the measured capacity where it crosses zero.
    """
    colors = {"M3": "C0", "M4": "C1"}
    cells = sorted(next(iter(preds.values())).cell.unique())
    fig, axes = plt.subplots(2, 4, figsize=(12, 5.6), sharex=True, sharey=True)
    for ax, cell in zip(axes.flat, cells):
        ax.axhline(0, color="k", lw=0.8)
        for name, pred in preds.items():
            g = pred[(pred.cell == cell) & pred.pred.notna()].sort_values("cycle")
            col = colors.get(name, "C3")
            err = 100 * (g.pred - g.capacity) / g.c0
            half = 100 * Z95 * g["std"] / g.c0
            inside = (err.abs() <= half).mean()
            ax.fill_between(g.cycle, err - half, err + half, color=col, alpha=0.25, lw=0)
            ax.plot(g.cycle, err, color=col, lw=1.0,
                    label=f"{name} {g.v1.iloc[0]:.1f}-{g.v2.iloc[0]:.1f} V, covers {100 * inside:.0f} %")
        ax.set_title(f"Cell {cell} (held out)", fontsize=9)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=6.5, loc="lower left")
    ax.set_ylim(-4, 4)
    for ax in axes[1]:
        ax.set_xlabel("Cycle")
    fig.supylabel("Predicted - measured [SOH points]", fontsize=10)
    names = " vs ".join(preds)
    fig.suptitle(
        f"{names}: held-out error with 95 % predictive band (nested, {regime}-width regime); "
        "band crossing zero = measurement covered"
    )
    save_fig(fig, "predictions_gpr.png")


def degraded(summary: pd.DataFrame, models=("M1", "M2", "M3", "M4", "M5"), baseline_models=("M1", "M3")) -> None:
    """Held-out RMSE at each level of each degradation sweep, one line per model.

    Solid: the project's window detector. Dashed: the first-crossing baseline, for
    the ΔQ-only models (the IC models change little). Levels where a model answers
    under 100 % of traces are labelled with the answer rate; levels with no answers
    are marked on the x axis.
    """
    base = summary[summary.detector == "first-crossing"]
    summary = summary[summary.detector == "time-below"]
    colors = {"M1": "C0", "M2": "C1", "M3": "C2", "M4": "C3", "M5": "C4"}
    panels = [
        ("Voltage noise sigma [mV]", ["clean", "noise 1 mV", "noise 2 mV", "noise 5 mV", "noise 10 mV"], ["0", "1", "2", "5", "10"]),
        ("Sample period [s]", ["period 1 s", "period 10 s", "period 30 s", "period 60 s"], ["1", "10", "30", "60"]),
        ("Voltage offset [mV]", ["offset -5 mV", "clean", "offset +5 mV"], ["-5", "0", "+5"]),
        ("ADC LSB [mV]", ["clean", "LSB 1 mV", "LSB 5 mV"], ["raw", "1", "5"]),
        ("Combined:\n2 mV, 1 mV LSB, 10 s", ["clean", "combined"], ["clean", "combined"]),
    ]
    fig, axes = plt.subplots(1, len(panels), figsize=(16, 4.2), gridspec_kw=dict(width_ratios=[5, 4, 3, 3, 2.4]))
    for ax, (title, cases, ticks) in zip(axes, panels):
        x = range(len(cases))
        for m in baseline_models:
            g = base[base.model == m].set_index("case").loc[cases]
            ax.plot(x, g.rmse, "--", lw=1.1, color=colors[m], alpha=0.8,
                    label=f"{m}, first-crossing detector" if ax is axes[0] else None)
        for m in models:
            g = summary[summary.model == m].set_index("case").loc[cases]
            ax.plot(x, g.rmse, "-o", ms=4, color=colors[m], label=m if ax is axes[0] else None)
            for xi, (rate, rmse) in enumerate(zip(g.answer_rate, g.rmse)):
                if rate == 0:
                    ax.plot(xi, 0, "x", color=colors[m], ms=9, mew=2, clip_on=False)
                    ax.annotate(f"{m}: none answered", (xi, 0), xytext=(-4, 8 + 12 * models.index(m)),
                                textcoords="offset points", fontsize=7, color=colors[m], ha="right")
                elif rate < 1:
                    ax.annotate(f"{100 * rate:.0f} %", (xi, rmse), xytext=(4, 2), textcoords="offset points",
                                fontsize=7, color=colors[m])
        ax.set_xticks(list(x), ticks, fontsize=8)
        ax.set_xlim(-0.4, len(cases) - 0.6)
        ax.set_ylim(bottom=0)
        ax.set_xlabel(title)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("Held-out RMSE [SOH points]")
    axes[0].legend(fontsize=8, loc="upper left")
    fig.suptitle("Frozen fold models (any-width windows) on degraded copies of their held-out cell; "
                 "dashed: old first-crossing detector; answer rate is 100 % unless marked")
    save_fig(fig, "degraded.png")
