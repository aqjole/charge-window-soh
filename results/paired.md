# Paired comparison: model vs control

Each model is compared with its control (`adds` names what the model adds) on the held-out traces both answered, each model at its own selected window. Decision rule fixed in advance: the addition helps only if the model has lower RMSE than its control in at least 7 of 8 held-out cells (one-sided sign test). In regime `any` the two models may use different windows, so a gain there can come partly from a longer window; the `wNNN` rows compare at equal width.

| model   | base   | adds         | regime   |   n_common |   rmse_base |   rmse_model |   macro_rmse_base |   macro_rmse_model |   cells_model_better |   n_cells |   sign_test_p | verdict                  |
|:--------|:-------|:-------------|:---------|-----------:|------------:|-------------:|------------------:|-------------------:|---------------------:|----------:|--------------:|:-------------------------|
| M2      | M1     | IC peak      | any      |    519.000 |       0.672 |        0.506 |             0.677 |              0.462 |                8.000 |     8.000 |         0.004 | helps                    |
| M2      | M1     | IC peak      | w100     |    nan     |     nan     |      nan     |           nan     |            nan     |              nan     |   nan     |       nan     | n/a (no eligible window) |
| M2      | M1     | IC peak      | w200     |    519.000 |       0.572 |        0.676 |             0.575 |              0.617 |                5.000 |     8.000 |         0.363 | no detectable gain       |
| M2      | M1     | IC peak      | w300     |    519.000 |       0.581 |        0.603 |             0.578 |              0.545 |                6.000 |     8.000 |         0.145 | no detectable gain       |
| M2      | M1     | IC peak      | w400     |    519.000 |       0.589 |        0.506 |             0.578 |              0.462 |                8.000 |     8.000 |         0.004 | helps                    |
| M4      | M3     | IC peak      | any      |    519.000 |       0.454 |        0.306 |             0.428 |              0.298 |                6.000 |     8.000 |         0.145 | no detectable gain       |
| M4      | M3     | IC peak      | w100     |    nan     |     nan     |      nan     |           nan     |            nan     |              nan     |   nan     |       nan     | n/a (no eligible window) |
| M4      | M3     | IC peak      | w200     |    519.000 |       0.641 |        0.390 |             0.576 |              0.359 |                7.000 |     8.000 |         0.035 | helps                    |
| M4      | M3     | IC peak      | w300     |    519.000 |       0.721 |        0.344 |             0.715 |              0.326 |                8.000 |     8.000 |         0.004 | helps                    |
| M4      | M3     | IC peak      | w400     |    519.000 |       0.447 |        0.306 |             0.423 |              0.298 |                6.000 |     8.000 |         0.145 | no detectable gain       |
| M5      | M3     | two segments | any      |    519.000 |       0.454 |        0.407 |             0.428 |              0.386 |                6.000 |     8.000 |         0.145 | no detectable gain       |
| M5      | M3     | two segments | w100     |    519.000 |       0.606 |        0.616 |             0.551 |              0.566 |                5.000 |     8.000 |         0.363 | no detectable gain       |
| M5      | M3     | two segments | w200     |    519.000 |       0.641 |        0.515 |             0.576 |              0.490 |                5.000 |     8.000 |         0.363 | no detectable gain       |
| M5      | M3     | two segments | w300     |    519.000 |       0.721 |        0.949 |             0.715 |              0.787 |                6.000 |     8.000 |         0.145 | no detectable gain       |
| M5      | M3     | two segments | w400     |    519.000 |       0.447 |        0.344 |             0.423 |              0.332 |                6.000 |     8.000 |         0.145 | no detectable gain       |
