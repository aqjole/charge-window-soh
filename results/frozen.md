# Frozen M1 estimator

The deployable M1 estimator: window chosen by leave-one-cell-out over all 8 cells with the nested-validation rule (mean per-cell RMSE, >= 95 % answer rate, ties to the narrower window, then the lower V1), then M1 fit on all 8 cells: capacity [mAh] = a_mah + b * dq [mAh]. selection_score is that criterion in SOH points, computed on the same cells that chose the window, so it is not an accuracy estimate; the reported accuracy is the nested result. The exact coefficients are in `c/soh_model.h` and in `frozen.csv` (written at full precision).

| model   |   v1 |   v2 |   width_mv |   a_mah |       b |   selection_score |   answer_rate |   n_train |
|:--------|-----:|-----:|-----------:|--------:|--------:|------------------:|--------------:|----------:|
| M1      |  3.8 |    4 |        200 | 91.9254 | 1.98688 |          0.575123 |             1 |       519 |
