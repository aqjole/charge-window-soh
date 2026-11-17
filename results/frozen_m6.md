# Frozen M6 estimator

The deployable M6 estimator: window chosen by leave-one-cell-out over all 8 cells with the nested-validation rule, then M6 (GPR on dq_a, dq_b) fit on all 8 cells and their offset-shifted copies. n_train counts the GPR training points (measured traces and copies), n_measured the measured traces among them. Length scales are on standardized inputs. selection_score is the criterion in SOH points on the same cells that chose the window, not an accuracy estimate; the reported accuracy is the nested result. The C header `c/soh_model_m6.h` holds the predictive-mean parameters (header_kb is its size).

| model   |    v1 |    v2 |   width_mv |   selection_score |   answer_rate |   n_train |   n_measured |   length_scale_a |   length_scale_b |   amplitude |   header_kb |
|:--------|------:|------:|-----------:|------------------:|--------------:|----------:|-------------:|-----------------:|-----------------:|------------:|------------:|
| M6      | 3.600 | 4.000 |        400 |             0.361 |         1.000 |      1557 |          519 |            3.937 |            3.492 |       3.066 |         108 |
