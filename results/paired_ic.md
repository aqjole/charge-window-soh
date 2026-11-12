# Paired comparison: IC model vs control

Each pair compared on the held-out traces both models answered, each model at its own selected window. Decision rule fixed in advance: IC helps only if the IC model has lower RMSE in at least 7 of 8 held-out cells (one-sided sign test). In regime `any` the two models may use different windows, so a gain there can come partly from a longer window; the `wNNN` rows compare at equal width.

| ic_model   | base_model   | regime   |   n_common |   rmse_base |   rmse_ic |   macro_rmse_base |   macro_rmse_ic |   cells_ic_better |   n_cells |   sign_test_p | verdict                  |
|:-----------|:-------------|:---------|-----------:|------------:|----------:|------------------:|----------------:|------------------:|----------:|--------------:|:-------------------------|
| M2         | M1           | any      |    519.000 |       0.674 |     0.506 |             0.680 |           0.462 |             8.000 |     8.000 |         0.004 | IC helps                 |
| M2         | M1           | w100     |    nan     |     nan     |   nan     |           nan     |         nan     |           nan     |   nan     |       nan     | n/a (no eligible window) |
| M2         | M1           | w200     |    519.000 |       0.576 |     0.677 |             0.579 |           0.618 |             5.000 |     8.000 |         0.363 | no detectable gain       |
| M2         | M1           | w300     |    519.000 |       0.585 |     0.604 |             0.582 |           0.545 |             6.000 |     8.000 |         0.145 | no detectable gain       |
| M2         | M1           | w400     |    519.000 |       0.589 |     0.506 |             0.578 |           0.462 |             8.000 |     8.000 |         0.004 | IC helps                 |
