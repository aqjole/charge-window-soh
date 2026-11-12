# Paired comparison per cell

Each pair compared on the held-out traces both models answered, each model at its own selected window. Decision rule fixed in advance: IC helps only if the IC model has lower RMSE in at least 7 of 8 held-out cells (one-sided sign test). In regime `any` the two models may use different windows, so a gain there can come partly from a longer window; the `wNNN` rows compare at equal width.

| ic_model   | base_model   | regime   |   cell |      n |   rmse_base |   rmse_ic | ic_better   |
|:-----------|:-------------|:---------|-------:|-------:|------------:|----------:|:------------|
| M2         | M1           | any      |      1 | 78.000 |       0.543 |     0.145 | True        |
| M2         | M1           | any      |      2 | 73.000 |       0.741 |     0.589 | True        |
| M2         | M1           | any      |      3 | 76.000 |       0.343 |     0.141 | True        |
| M2         | M1           | any      |      4 | 47.000 |       0.845 |     0.608 | True        |
| M2         | M1           | any      |      5 | 46.000 |       1.154 |     1.100 | True        |
| M2         | M1           | any      |      6 | 46.000 |       0.765 |     0.430 | True        |
| M2         | M1           | any      |      7 | 77.000 |       0.546 |     0.518 | True        |
| M2         | M1           | any      |      8 | 76.000 |       0.501 |     0.167 | True        |
| M2         | M1           | w200     |      1 | 78.000 |       0.448 |     0.201 | True        |
| M2         | M1           | w200     |      2 | 73.000 |       0.741 |     0.594 | True        |
| M2         | M1           | w200     |      3 | 76.000 |       0.343 |     0.170 | True        |
| M2         | M1           | w200     |      4 | 47.000 |       0.693 |     1.040 | False       |
| M2         | M1           | w200     |      5 | 46.000 |       0.877 |     1.250 | False       |
| M2         | M1           | w200     |      6 | 46.000 |       0.652 |     0.565 | True        |
| M2         | M1           | w200     |      7 | 77.000 |       0.376 |     0.930 | False       |
| M2         | M1           | w200     |      8 | 76.000 |       0.501 |     0.193 | True        |
| M2         | M1           | w300     |      1 | 78.000 |       0.543 |     0.204 | True        |
| M2         | M1           | w300     |      2 | 73.000 |       0.769 |     0.621 | True        |
| M2         | M1           | w300     |      3 | 76.000 |       0.349 |     0.194 | True        |
| M2         | M1           | w300     |      4 | 47.000 |       0.845 |     0.671 | True        |
| M2         | M1           | w300     |      5 | 46.000 |       0.534 |     1.393 | False       |
| M2         | M1           | w300     |      6 | 46.000 |       0.765 |     0.433 | True        |
| M2         | M1           | w300     |      7 | 77.000 |       0.357 |     0.657 | False       |
| M2         | M1           | w300     |      8 | 76.000 |       0.495 |     0.189 | True        |
| M2         | M1           | w400     |      1 | 78.000 |       0.411 |     0.145 | True        |
| M2         | M1           | w400     |      2 | 73.000 |       0.654 |     0.589 | True        |
| M2         | M1           | w400     |      3 | 76.000 |       0.275 |     0.141 | True        |
| M2         | M1           | w400     |      4 | 47.000 |       0.712 |     0.608 | True        |
| M2         | M1           | w400     |      5 | 46.000 |       1.154 |     1.100 | True        |
| M2         | M1           | w400     |      6 | 46.000 |       0.582 |     0.430 | True        |
| M2         | M1           | w400     |      7 | 77.000 |       0.546 |     0.518 | True        |
| M2         | M1           | w400     |      8 | 76.000 |       0.292 |     0.167 | True        |
