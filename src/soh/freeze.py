"""Freeze the deployable M1 and M6 estimators and write their C headers.

For each model the window is chosen with the same rule used inside each outer
fold, now over all 8 cells: leave-one-cell-out score (mean per-cell RMSE),
eligible only at >= 95 % answer rate, ties to the narrower window and then the
lower V1. The model is then fit on all 8 cells at that window:

- M1: C = a + b * dq, written to `c/soh_model.h`;
- M6: the GPR on (dq_a, dq_b), trained also on the offset-shifted copies, written
  to `c/soh_model_m6.h` as the data its predictive mean needs: training inputs
  divided by the length scales, the weights alpha, the input scaler, the kernel
  amplitude and the target mean and std. The predictive std needs the n x n
  Cholesky factor and is not exported. The fitted sklearn model is also pickled to
  `build/` for the agreement check; it is build output and not committed.

These are the models a BMS would ship. Their accuracy is not measured here: the
score is the selection criterion over the same cells, and the reported accuracy
remains the nested result in `results/clean_nested.md`.
"""

from __future__ import annotations

from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from threadpoolctl import threadpool_limits

from soh import NOMINAL_CURRENT_MA
from soh.features import ARM_BAND_V, END_BAND_V, MAX_GAP_S
from soh.load import load
from soh.report import ROOT, RESULTS, write_table
from soh.validate import Win, feature_table, fit_model, fit_predict, metrics, n_jobs, select, window_grid

MODEL = "M1"
HEADER = ROOT / "c" / "soh_model.h"
GPR_MODEL = "M6"
GPR_HEADER = ROOT / "c" / "soh_model_m6.h"
GPR_PICKLE = ROOT / "build" / "frozen_m6.joblib"


@dataclass(frozen=True)
class Frozen:
    win: Win
    a_mah: float  # intercept
    b: float  # slope, mAh of capacity per mAh of dq


def selection_scores(features: dict[Win, pd.DataFrame], model: str = MODEL) -> pd.DataFrame:
    """Leave-one-cell-out score of every window over all cells (one row per window).

    The fits run in parallel for GPR models; each is deterministic, so the order
    does not matter.
    """
    cells = sorted(next(iter(features.values())).cell.unique())
    tasks = [(win, h) for win in features for h in cells]
    preds = Parallel(n_jobs=n_jobs(model))(
        delayed(fit_predict)(features[win], model, [h], [c for c in cells if c != h]) for win, h in tasks
    )
    rows = []
    for win in features:
        m = metrics(pd.concat([p for (w, _), p in zip(tasks, preds) if w == win], ignore_index=True))
        rows.append(
            dict(fold=0, v1=win.v1, v2=win.v2, width_mv=win.width_mv, score=m["macro_rmse"], answer_rate=m["answer_rate"])
        )
    return pd.DataFrame(rows)


def select_and_fit(features: dict[Win, pd.DataFrame], model: str):
    """(window, model fit on all cells at that window, scores of every window)."""
    scores = selection_scores(features, model)
    best = select(scores, "any").iloc[0]
    win = Win(best.v1, best.v2)
    df = features[win]
    with threadpool_limits(1):  # one BLAS thread: the fit, and so the generated header, is reproducible
        est = fit_model(df, model, sorted(df.cell.unique()))
    return win, est, scores


def freeze(features: dict[Win, pd.DataFrame], model: str = MODEL) -> tuple[Frozen, pd.DataFrame]:
    win, est, scores = select_and_fit(features, model)
    return Frozen(win, float(est.intercept_), float(est.coef_[0])), scores


@dataclass(frozen=True)
class FrozenGPR:
    """What the GPR predictive mean needs, in the order sklearn computes it:
    z = ((x - x_mean) / x_scale) / length_scale; r_i = |z - z_train_i|;
    mean = y_std * sum_i amplitude * matern52(r_i) * alpha_i + y_mean."""

    win: Win
    x_mean: np.ndarray  # (2,)
    x_scale: np.ndarray  # (2,)
    length_scale: np.ndarray  # (2,)
    amplitude: float
    y_mean: float
    y_std: float
    z_train: np.ndarray  # (n, 2), training inputs after scaling, divided by length_scale
    alpha: np.ndarray  # (n,)


def gpr_params(win: Win, est) -> FrozenGPR:
    """Extract the predictive-mean parameters of a `models.gpr` pipeline."""
    scaler, g = est[0], est[-1]
    prod = g.kernel_.k1  # Sum(Product(Constant, Matern), White)
    const, matern = prod.k1, prod.k2
    if matern.nu != 2.5:
        raise ValueError(f"expected Matern 5/2, got nu={matern.nu}")
    ls = np.broadcast_to(np.asarray(matern.length_scale, dtype=float), (g.X_train_.shape[1],)).copy()
    return FrozenGPR(
        win=win,
        x_mean=scaler.mean_.copy(),
        x_scale=scaler.scale_.copy(),
        length_scale=ls,
        amplitude=float(const.constant_value),
        y_mean=float(np.ravel(g._y_train_mean)[0]),
        y_std=float(np.ravel(g._y_train_std)[0]),
        z_train=g.X_train_ / ls,
        alpha=np.ravel(g.alpha_).copy(),
    )


def gpr_predict(p: FrozenGPR, x: np.ndarray) -> np.ndarray:
    """Predictive mean from the exported parameters only (NumPy reference of the C code)."""
    z = ((np.atleast_2d(x) - p.x_mean) / p.x_scale) / p.length_scale
    r = np.sqrt(5.0) * np.sqrt(((z[:, None, :] - p.z_train[None, :, :]) ** 2).sum(-1))
    k = p.amplitude * (1.0 + r + r**2 / 3.0) * np.exp(-r)
    return p.y_std * (k @ p.alpha) + p.y_mean


def gpr_header_text(p: FrozenGPR) -> str:
    """C header for `c/soh_est.h`'s `soh_gpr`, every double as its shortest round-trip repr."""
    g = lambda x: repr(float(x))  # noqa: E731
    mv = lambda x: g(round(1000 * x, 6))  # noqa: E731
    pair = lambda a: "{" + ", ".join(g(x) for x in a) + "}"  # noqa: E731
    n = len(p.alpha)
    z = ",\n".join(f"    {g(a)}, {g(b)}" for a, b in p.z_train)
    alpha = ",\n".join(f"    {g(a)}" for a in p.alpha)
    return "\n".join(
        [
            "/* Generated by `python -m soh.freeze`. Do not edit. */",
            "/* M6: GPR predictive mean on (dq_a, dq_b), Matern 5/2 kernel. */",
            "#ifndef SOH_MODEL_M6_H",
            "#define SOH_MODEL_M6_H",
            "",
            '#include "soh_est.h"',
            "",
            f"#define SOH_M6_V1_MV {mv(p.win.v1)}",
            f"#define SOH_M6_V2_MV {mv(p.win.v2)}",
            f"#define SOH_M6_N_TRAIN {n}",
            "",
            "/* training inputs: standardized, then divided by the length scales; row-major (n, 2) */",
            "static const double soh_m6_z_train[2 * SOH_M6_N_TRAIN] = {",
            z,
            "};",
            "",
            "static const double soh_m6_alpha[SOH_M6_N_TRAIN] = {",
            alpha,
            "};",
            "",
            "static const soh_gpr soh_m6_gpr = {",
            "    SOH_M6_N_TRAIN,",
            f"    {pair(p.x_mean)}, /* x_mean */",
            f"    {pair(p.x_scale)}, /* x_scale */",
            f"    {pair(p.length_scale)}, /* length_scale */",
            f"    {g(p.amplitude)}, /* amplitude */",
            f"    {g(p.y_mean)}, /* y_mean [mAh] */",
            f"    {g(p.y_std)}, /* y_std [mAh] */",
            "    soh_m6_z_train,",
            "    soh_m6_alpha,",
            "};",
            "",
            "#endif",
            "",
        ]
    )


def header_text(f: Frozen) -> str:
    """C header with the frozen configuration as double literals.

    `repr` is the shortest string that round-trips, so the compiler reads back the
    same doubles. Voltages are converted to mV and rounded to 1 nV to drop the
    binary noise of the V -> mV product.
    """
    g = lambda x: repr(float(x))  # noqa: E731
    mv = lambda x: g(round(1000 * x, 6))  # noqa: E731
    return "\n".join(
        [
            "/* Generated by `python -m soh.freeze`. Do not edit. */",
            "#ifndef SOH_MODEL_H",
            "#define SOH_MODEL_H",
            "",
            f"#define SOH_MODEL_V1_MV {mv(f.win.v1)}",
            f"#define SOH_MODEL_V2_MV {mv(f.win.v2)}",
            f"#define SOH_MODEL_ARM_BAND_MV {mv(ARM_BAND_V)}",
            f"#define SOH_MODEL_END_BAND_MV {mv(END_BAND_V)}",
            f"#define SOH_MODEL_MAX_GAP_S {g(MAX_GAP_S)}",
            f"#define SOH_MODEL_CURRENT_MA {g(NOMINAL_CURRENT_MA)}",
            f"#define SOH_MODEL_A_MAH {g(f.a_mah)}",
            f"#define SOH_MODEL_B {g(f.b)}",
            "",
            "#endif",
            "",
        ]
    )


def load_frozen() -> Frozen:
    """The frozen model as written to `results/frozen.csv` by `main`."""
    r = pd.read_csv(RESULTS / "frozen.csv").iloc[0]
    return Frozen(Win(float(r.v1), float(r.v2)), float(r.a_mah), float(r.b))


def freeze_gpr(curves, grid: list[Win]) -> None:
    """Select, fit and write the frozen M6: header, pickle, results tables."""
    features = {w: feature_table(curves, w, augment=True) for w in grid}
    win, est, scores = select_and_fit(features, GPR_MODEL)
    p = gpr_params(win, est)
    GPR_HEADER.write_text(gpr_header_text(p))
    GPR_PICKLE.parent.mkdir(exist_ok=True)
    joblib.dump((win, est), GPR_PICKLE)

    chosen = scores[(scores.v1 == win.v1) & (scores.v2 == win.v2)].iloc[0]
    df = features[win]
    row = pd.DataFrame(
        [
            dict(
                model=GPR_MODEL, v1=win.v1, v2=win.v2, width_mv=win.width_mv,
                selection_score=chosen.score, answer_rate=chosen.answer_rate,
                n_train=len(p.alpha), n_measured=int(((df.aug == 0) & (df.reason == "OK")).sum()),
                length_scale_a=p.length_scale[0], length_scale_b=p.length_scale[1],
                amplitude=p.amplitude, header_kb=round(GPR_HEADER.stat().st_size / 1024),
            )
        ]
    )
    note = (
        "The deployable M6 estimator: window chosen by leave-one-cell-out over all 8 cells with the "
        "nested-validation rule, then M6 (GPR on dq_a, dq_b) fit on all 8 cells and their offset-shifted "
        "copies. n_train counts the GPR training points (measured traces and copies), n_measured the "
        "measured traces among them. Length scales are on standardized inputs. selection_score is the "
        "criterion in SOH points on the same cells that chose the window, not an accuracy estimate; the "
        "reported accuracy is the nested result. The C header `c/soh_model_m6.h` holds the predictive-mean "
        "parameters (header_kb is its size)."
    )
    write_table(row, "frozen_m6", "Frozen M6 estimator", note)
    write_table(
        scores.drop(columns="fold").rename(columns={"score": "selection_score"}),
        "frozen_m6_scores",
        "Frozen M6: window selection scores",
        "Selection criterion for the frozen M6 window: leave-one-cell-out over all 8 cells, per window. "
        "score = mean per-cell RMSE in SOH points.",
    )
    print(row.to_string(index=False))
    print(f"wrote {GPR_HEADER.relative_to(ROOT)}")


def load_frozen_gpr():
    """(window, fitted M6) as pickled by `freeze_gpr`."""
    return joblib.load(GPR_PICKLE)


def main() -> None:
    curves, audit = load()
    grid = window_grid(round(audit.cutoff_v[0], 2))
    features = {w: feature_table(curves, w) for w in grid}
    f, scores = freeze(features)

    HEADER.parent.mkdir(exist_ok=True)
    HEADER.write_text(header_text(f))

    chosen = scores[(scores.v1 == f.win.v1) & (scores.v2 == f.win.v2)].iloc[0]
    row = pd.DataFrame(
        [
            dict(
                model=MODEL, v1=f.win.v1, v2=f.win.v2, width_mv=f.win.width_mv, a_mah=f.a_mah, b=f.b,
                selection_score=chosen.score, answer_rate=chosen.answer_rate,
                n_train=int((features[f.win].reason == "OK").sum()),
            )
        ]
    )
    note = (
        "The deployable M1 estimator: window chosen by leave-one-cell-out over all 8 cells with the "
        "nested-validation rule (mean per-cell RMSE, >= 95 % answer rate, ties to the narrower window, "
        "then the lower V1), then M1 fit on all 8 cells: capacity [mAh] = a_mah + b * dq [mAh]. "
        "selection_score is that criterion in SOH points, computed on the same cells that chose the "
        "window, so it is not an accuracy estimate; the reported accuracy is the nested result. "
        "The exact coefficients are in `c/soh_model.h` and in `frozen.csv` (written at full precision)."
    )
    # shortest round-trip repr: the coefficients here and in the C header are the same doubles
    RESULTS.mkdir(exist_ok=True)
    row.to_csv(RESULTS / "frozen.csv", index=False, lineterminator="\n")
    md = ["# Frozen M1 estimator", "", note, "", row.to_markdown(index=False, floatfmt=".6g"), ""]
    (RESULTS / "frozen.md").write_text("\n".join(md))
    score_note = (
        "Selection criterion for the frozen M1 window: leave-one-cell-out over all 8 cells, per window. "
        "score = mean per-cell RMSE in SOH points."
    )
    write_table(
        scores.drop(columns="fold").rename(columns={"score": "selection_score"}),
        "frozen_scores",
        "Frozen M1: window selection scores",
        score_note,
    )
    print(row.to_string(index=False))
    print(f"wrote {HEADER.relative_to(ROOT)}")

    freeze_gpr(curves, grid)


if __name__ == "__main__":
    main()
