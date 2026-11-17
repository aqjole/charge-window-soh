# Paired comparison per cell

Each model is compared with its control (`adds` names what the model adds) on the held-out traces both answered, each model at its own selected window. Decision rule fixed in advance: the addition helps only if the model has lower RMSE than its control in at least 7 of 8 held-out cells (one-sided sign test). In regime `any` the two models may use different windows, so a gain there can come partly from a longer window; the `wNNN` rows compare at equal width.

| model   | base   | adds                          | regime   |   cell |      n |   rmse_base |   rmse_model | model_better   |
|:--------|:-------|:------------------------------|:---------|-------:|-------:|------------:|-------------:|:---------------|
| M2      | M1     | IC peak                       | any      |      1 | 78.000 |       0.543 |        0.145 | True           |
| M2      | M1     | IC peak                       | any      |      2 | 73.000 |       0.738 |        0.589 | True           |
| M2      | M1     | IC peak                       | any      |      3 | 76.000 |       0.342 |        0.141 | True           |
| M2      | M1     | IC peak                       | any      |      4 | 47.000 |       0.837 |        0.608 | True           |
| M2      | M1     | IC peak                       | any      |      5 | 46.000 |       1.154 |        1.100 | True           |
| M2      | M1     | IC peak                       | any      |      6 | 46.000 |       0.764 |        0.430 | True           |
| M2      | M1     | IC peak                       | any      |      7 | 77.000 |       0.544 |        0.518 | True           |
| M2      | M1     | IC peak                       | any      |      8 | 76.000 |       0.498 |        0.167 | True           |
| M2      | M1     | IC peak                       | w200     |      1 | 78.000 |       0.444 |        0.201 | True           |
| M2      | M1     | IC peak                       | w200     |      2 | 73.000 |       0.738 |        0.595 | True           |
| M2      | M1     | IC peak                       | w200     |      3 | 76.000 |       0.342 |        0.169 | True           |
| M2      | M1     | IC peak                       | w200     |      4 | 47.000 |       0.684 |        1.039 | False          |
| M2      | M1     | IC peak                       | w200     |      5 | 46.000 |       0.873 |        1.249 | False          |
| M2      | M1     | IC peak                       | w200     |      6 | 46.000 |       0.651 |        0.565 | True           |
| M2      | M1     | IC peak                       | w200     |      7 | 77.000 |       0.370 |        0.928 | False          |
| M2      | M1     | IC peak                       | w200     |      8 | 76.000 |       0.498 |        0.191 | True           |
| M2      | M1     | IC peak                       | w300     |      1 | 78.000 |       0.543 |        0.205 | True           |
| M2      | M1     | IC peak                       | w300     |      2 | 73.000 |       0.767 |        0.622 | True           |
| M2      | M1     | IC peak                       | w300     |      3 | 76.000 |       0.346 |        0.194 | True           |
| M2      | M1     | IC peak                       | w300     |      4 | 47.000 |       0.837 |        0.670 | True           |
| M2      | M1     | IC peak                       | w300     |      5 | 46.000 |       0.530 |        1.392 | False          |
| M2      | M1     | IC peak                       | w300     |      6 | 46.000 |       0.764 |        0.432 | True           |
| M2      | M1     | IC peak                       | w300     |      7 | 77.000 |       0.348 |        0.656 | False          |
| M2      | M1     | IC peak                       | w300     |      8 | 76.000 |       0.491 |        0.189 | True           |
| M2      | M1     | IC peak                       | w400     |      1 | 78.000 |       0.413 |        0.145 | True           |
| M2      | M1     | IC peak                       | w400     |      2 | 73.000 |       0.654 |        0.589 | True           |
| M2      | M1     | IC peak                       | w400     |      3 | 76.000 |       0.275 |        0.141 | True           |
| M2      | M1     | IC peak                       | w400     |      4 | 47.000 |       0.711 |        0.608 | True           |
| M2      | M1     | IC peak                       | w400     |      5 | 46.000 |       1.154 |        1.100 | True           |
| M2      | M1     | IC peak                       | w400     |      6 | 46.000 |       0.581 |        0.430 | True           |
| M2      | M1     | IC peak                       | w400     |      7 | 77.000 |       0.544 |        0.518 | True           |
| M2      | M1     | IC peak                       | w400     |      8 | 76.000 |       0.293 |        0.167 | True           |
| M4      | M3     | IC peak                       | any      |      1 | 78.000 |       0.296 |        0.181 | True           |
| M4      | M3     | IC peak                       | any      |      2 | 73.000 |       0.619 |        0.400 | True           |
| M4      | M3     | IC peak                       | any      |      3 | 76.000 |       0.140 |        0.208 | False          |
| M4      | M3     | IC peak                       | any      |      4 | 47.000 |       0.648 |        0.326 | True           |
| M4      | M3     | IC peak                       | any      |      5 | 46.000 |       0.334 |        0.436 | False          |
| M4      | M3     | IC peak                       | any      |      6 | 46.000 |       0.487 |        0.297 | True           |
| M4      | M3     | IC peak                       | any      |      7 | 77.000 |       0.605 |        0.388 | True           |
| M4      | M3     | IC peak                       | any      |      8 | 76.000 |       0.296 |        0.152 | True           |
| M4      | M3     | IC peak                       | w200     |      1 | 78.000 |       0.368 |        0.237 | True           |
| M4      | M3     | IC peak                       | w200     |      2 | 73.000 |       0.619 |        0.570 | True           |
| M4      | M3     | IC peak                       | w200     |      3 | 76.000 |       0.310 |        0.269 | True           |
| M4      | M3     | IC peak                       | w200     |      4 | 47.000 |       0.477 |        0.381 | True           |
| M4      | M3     | IC peak                       | w200     |      5 | 46.000 |       1.658 |        0.358 | True           |
| M4      | M3     | IC peak                       | w200     |      6 | 46.000 |       0.534 |        0.282 | True           |
| M4      | M3     | IC peak                       | w200     |      7 | 77.000 |       0.241 |        0.580 | False          |
| M4      | M3     | IC peak                       | w200     |      8 | 76.000 |       0.405 |        0.197 | True           |
| M4      | M3     | IC peak                       | w300     |      1 | 78.000 |       0.451 |        0.219 | True           |
| M4      | M3     | IC peak                       | w300     |      2 | 73.000 |       0.546 |        0.509 | True           |
| M4      | M3     | IC peak                       | w300     |      3 | 76.000 |       0.348 |        0.243 | True           |
| M4      | M3     | IC peak                       | w300     |      4 | 47.000 |       1.022 |        0.356 | True           |
| M4      | M3     | IC peak                       | w300     |      5 | 46.000 |       1.340 |        0.372 | True           |
| M4      | M3     | IC peak                       | w300     |      6 | 46.000 |       0.712 |        0.291 | True           |
| M4      | M3     | IC peak                       | w300     |      7 | 77.000 |       0.804 |        0.455 | True           |
| M4      | M3     | IC peak                       | w300     |      8 | 76.000 |       0.493 |        0.165 | True           |
| M4      | M3     | IC peak                       | w400     |      1 | 78.000 |       0.296 |        0.181 | True           |
| M4      | M3     | IC peak                       | w400     |      2 | 73.000 |       0.579 |        0.400 | True           |
| M4      | M3     | IC peak                       | w400     |      3 | 76.000 |       0.140 |        0.208 | False          |
| M4      | M3     | IC peak                       | w400     |      4 | 47.000 |       0.648 |        0.326 | True           |
| M4      | M3     | IC peak                       | w400     |      5 | 46.000 |       0.334 |        0.436 | False          |
| M4      | M3     | IC peak                       | w400     |      6 | 46.000 |       0.487 |        0.297 | True           |
| M4      | M3     | IC peak                       | w400     |      7 | 77.000 |       0.605 |        0.388 | True           |
| M4      | M3     | IC peak                       | w400     |      8 | 76.000 |       0.296 |        0.152 | True           |
| M5      | M3     | two segments                  | any      |      1 | 78.000 |       0.296 |        0.289 | True           |
| M5      | M3     | two segments                  | any      |      2 | 73.000 |       0.619 |        0.571 | True           |
| M5      | M3     | two segments                  | any      |      3 | 76.000 |       0.140 |        0.214 | False          |
| M5      | M3     | two segments                  | any      |      4 | 47.000 |       0.648 |        0.325 | True           |
| M5      | M3     | two segments                  | any      |      5 | 46.000 |       0.334 |        0.835 | False          |
| M5      | M3     | two segments                  | any      |      6 | 46.000 |       0.487 |        0.377 | True           |
| M5      | M3     | two segments                  | any      |      7 | 77.000 |       0.605 |        0.223 | True           |
| M5      | M3     | two segments                  | any      |      8 | 76.000 |       0.296 |        0.254 | True           |
| M5      | M3     | two segments                  | w100     |      1 | 78.000 |       0.422 |        0.531 | False          |
| M5      | M3     | two segments                  | w100     |      2 | 73.000 |       0.971 |        1.011 | False          |
| M5      | M3     | two segments                  | w100     |      3 | 76.000 |       0.392 |        0.336 | True           |
| M5      | M3     | two segments                  | w100     |      4 | 47.000 |       0.338 |        0.650 | False          |
| M5      | M3     | two segments                  | w100     |      5 | 46.000 |       1.177 |        1.051 | True           |
| M5      | M3     | two segments                  | w100     |      6 | 46.000 |       0.375 |        0.299 | True           |
| M5      | M3     | two segments                  | w100     |      7 | 77.000 |       0.319 |        0.249 | True           |
| M5      | M3     | two segments                  | w100     |      8 | 76.000 |       0.412 |        0.402 | True           |
| M5      | M3     | two segments                  | w200     |      1 | 78.000 |       0.368 |        0.260 | True           |
| M5      | M3     | two segments                  | w200     |      2 | 73.000 |       0.619 |        0.759 | False          |
| M5      | M3     | two segments                  | w200     |      3 | 76.000 |       0.310 |        0.312 | False          |
| M5      | M3     | two segments                  | w200     |      4 | 47.000 |       0.477 |        0.394 | True           |
| M5      | M3     | two segments                  | w200     |      5 | 46.000 |       1.658 |        0.835 | True           |
| M5      | M3     | two segments                  | w200     |      6 | 46.000 |       0.534 |        0.414 | True           |
| M5      | M3     | two segments                  | w200     |      7 | 77.000 |       0.241 |        0.575 | False          |
| M5      | M3     | two segments                  | w200     |      8 | 76.000 |       0.405 |        0.373 | True           |
| M5      | M3     | two segments                  | w300     |      1 | 78.000 |       0.451 |        0.529 | False          |
| M5      | M3     | two segments                  | w300     |      2 | 73.000 |       0.546 |        0.462 | True           |
| M5      | M3     | two segments                  | w300     |      3 | 76.000 |       0.348 |        0.239 | True           |
| M5      | M3     | two segments                  | w300     |      4 | 47.000 |       1.022 |        0.774 | True           |
| M5      | M3     | two segments                  | w300     |      5 | 46.000 |       1.340 |        2.690 | False          |
| M5      | M3     | two segments                  | w300     |      6 | 46.000 |       0.712 |        0.485 | True           |
| M5      | M3     | two segments                  | w300     |      7 | 77.000 |       0.804 |        0.754 | True           |
| M5      | M3     | two segments                  | w300     |      8 | 76.000 |       0.493 |        0.366 | True           |
| M5      | M3     | two segments                  | w400     |      1 | 78.000 |       0.296 |        0.289 | True           |
| M5      | M3     | two segments                  | w400     |      2 | 73.000 |       0.579 |        0.571 | True           |
| M5      | M3     | two segments                  | w400     |      3 | 76.000 |       0.140 |        0.214 | False          |
| M5      | M3     | two segments                  | w400     |      4 | 47.000 |       0.648 |        0.325 | True           |
| M5      | M3     | two segments                  | w400     |      5 | 46.000 |       0.334 |        0.404 | False          |
| M5      | M3     | two segments                  | w400     |      6 | 46.000 |       0.487 |        0.377 | True           |
| M5      | M3     | two segments                  | w400     |      7 | 77.000 |       0.605 |        0.223 | True           |
| M5      | M3     | two segments                  | w400     |      8 | 76.000 |       0.296 |        0.254 | True           |
| M6      | M5     | offset augmentation           | any      |      1 | 78.000 |       0.289 |        0.235 | True           |
| M6      | M5     | offset augmentation           | any      |      2 | 73.000 |       0.571 |        0.703 | False          |
| M6      | M5     | offset augmentation           | any      |      3 | 76.000 |       0.214 |        0.221 | False          |
| M6      | M5     | offset augmentation           | any      |      4 | 47.000 |       0.325 |        0.559 | False          |
| M6      | M5     | offset augmentation           | any      |      5 | 46.000 |       0.835 |        0.517 | True           |
| M6      | M5     | offset augmentation           | any      |      6 | 46.000 |       0.377 |        0.433 | False          |
| M6      | M5     | offset augmentation           | any      |      7 | 77.000 |       0.223 |        0.358 | False          |
| M6      | M5     | offset augmentation           | any      |      8 | 76.000 |       0.254 |        0.225 | True           |
| M6      | M5     | offset augmentation           | w100     |      1 | 78.000 |       0.531 |        0.373 | True           |
| M6      | M5     | offset augmentation           | w100     |      2 | 73.000 |       1.011 |        1.000 | True           |
| M6      | M5     | offset augmentation           | w100     |      3 | 76.000 |       0.336 |        0.298 | True           |
| M6      | M5     | offset augmentation           | w100     |      4 | 47.000 |       0.650 |        0.500 | True           |
| M6      | M5     | offset augmentation           | w100     |      5 | 46.000 |       1.051 |        0.472 | True           |
| M6      | M5     | offset augmentation           | w100     |      6 | 46.000 |       0.299 |        0.252 | True           |
| M6      | M5     | offset augmentation           | w100     |      7 | 77.000 |       0.249 |        0.280 | False          |
| M6      | M5     | offset augmentation           | w100     |      8 | 76.000 |       0.402 |        0.380 | True           |
| M6      | M5     | offset augmentation           | w200     |      1 | 78.000 |       0.260 |        0.208 | True           |
| M6      | M5     | offset augmentation           | w200     |      2 | 73.000 |       0.759 |        0.703 | True           |
| M6      | M5     | offset augmentation           | w200     |      3 | 76.000 |       0.312 |        0.182 | True           |
| M6      | M5     | offset augmentation           | w200     |      4 | 47.000 |       0.394 |        0.469 | False          |
| M6      | M5     | offset augmentation           | w200     |      5 | 46.000 |       0.835 |        0.695 | True           |
| M6      | M5     | offset augmentation           | w200     |      6 | 46.000 |       0.414 |        0.314 | True           |
| M6      | M5     | offset augmentation           | w200     |      7 | 77.000 |       0.575 |        0.436 | True           |
| M6      | M5     | offset augmentation           | w200     |      8 | 76.000 |       0.373 |        0.156 | True           |
| M6      | M5     | offset augmentation           | w300     |      1 | 78.000 |       0.529 |        0.629 | False          |
| M6      | M5     | offset augmentation           | w300     |      2 | 73.000 |       0.462 |        0.458 | True           |
| M6      | M5     | offset augmentation           | w300     |      3 | 76.000 |       0.239 |        0.257 | False          |
| M6      | M5     | offset augmentation           | w300     |      4 | 47.000 |       0.774 |        0.760 | True           |
| M6      | M5     | offset augmentation           | w300     |      5 | 46.000 |       2.690 |        0.336 | True           |
| M6      | M5     | offset augmentation           | w300     |      6 | 46.000 |       0.485 |        0.515 | False          |
| M6      | M5     | offset augmentation           | w300     |      7 | 77.000 |       0.754 |        0.754 | False          |
| M6      | M5     | offset augmentation           | w300     |      8 | 76.000 |       0.366 |        0.185 | True           |
| M6      | M5     | offset augmentation           | w400     |      1 | 78.000 |       0.289 |        0.235 | True           |
| M6      | M5     | offset augmentation           | w400     |      2 | 73.000 |       0.571 |        0.342 | True           |
| M6      | M5     | offset augmentation           | w400     |      3 | 76.000 |       0.214 |        0.221 | False          |
| M6      | M5     | offset augmentation           | w400     |      4 | 47.000 |       0.325 |        0.559 | False          |
| M6      | M5     | offset augmentation           | w400     |      5 | 46.000 |       0.404 |        0.517 | False          |
| M6      | M5     | offset augmentation           | w400     |      6 | 46.000 |       0.377 |        0.433 | False          |
| M6      | M5     | offset augmentation           | w400     |      7 | 77.000 |       0.223 |        0.358 | False          |
| M6      | M5     | offset augmentation           | w400     |      8 | 76.000 |       0.254 |        0.225 | True           |
| M8      | M6     | curve residual and noise copy | any      |      1 | 78.000 |       0.235 |        0.138 | True           |
| M8      | M6     | curve residual and noise copy | any      |      2 | 73.000 |       0.703 |        0.347 | True           |
| M8      | M6     | curve residual and noise copy | any      |      3 | 76.000 |       0.221 |        0.106 | True           |
| M8      | M6     | curve residual and noise copy | any      |      4 | 47.000 |       0.559 |        0.194 | True           |
| M8      | M6     | curve residual and noise copy | any      |      5 | 46.000 |       0.517 |        0.328 | True           |
| M8      | M6     | curve residual and noise copy | any      |      6 | 46.000 |       0.433 |        0.364 | True           |
| M8      | M6     | curve residual and noise copy | any      |      7 | 77.000 |       0.358 |        0.189 | True           |
| M8      | M6     | curve residual and noise copy | any      |      8 | 76.000 |       0.225 |        0.117 | True           |
| M8      | M6     | curve residual and noise copy | w100     |      1 | 78.000 |       0.373 |        0.250 | True           |
| M8      | M6     | curve residual and noise copy | w100     |      2 | 73.000 |       1.000 |        0.598 | True           |
| M8      | M6     | curve residual and noise copy | w100     |      3 | 76.000 |       0.298 |        0.225 | True           |
| M8      | M6     | curve residual and noise copy | w100     |      4 | 47.000 |       0.500 |        0.228 | True           |
| M8      | M6     | curve residual and noise copy | w100     |      5 | 46.000 |       0.472 |        0.668 | False          |
| M8      | M6     | curve residual and noise copy | w100     |      6 | 46.000 |       0.252 |        0.290 | False          |
| M8      | M6     | curve residual and noise copy | w100     |      7 | 77.000 |       0.280 |        0.234 | True           |
| M8      | M6     | curve residual and noise copy | w100     |      8 | 76.000 |       0.380 |        0.275 | True           |
| M8      | M6     | curve residual and noise copy | w200     |      1 | 78.000 |       0.208 |        0.291 | False          |
| M8      | M6     | curve residual and noise copy | w200     |      2 | 73.000 |       0.703 |        0.609 | True           |
| M8      | M6     | curve residual and noise copy | w200     |      3 | 76.000 |       0.182 |        0.215 | False          |
| M8      | M6     | curve residual and noise copy | w200     |      4 | 47.000 |       0.469 |        0.305 | True           |
| M8      | M6     | curve residual and noise copy | w200     |      5 | 46.000 |       0.695 |        0.580 | True           |
| M8      | M6     | curve residual and noise copy | w200     |      6 | 46.000 |       0.314 |        0.466 | False          |
| M8      | M6     | curve residual and noise copy | w200     |      7 | 77.000 |       0.436 |        0.345 | True           |
| M8      | M6     | curve residual and noise copy | w200     |      8 | 76.000 |       0.156 |        0.255 | False          |
| M8      | M6     | curve residual and noise copy | w300     |      1 | 78.000 |       0.629 |        0.178 | True           |
| M8      | M6     | curve residual and noise copy | w300     |      2 | 73.000 |       0.458 |        0.539 | False          |
| M8      | M6     | curve residual and noise copy | w300     |      3 | 76.000 |       0.257 |        0.159 | True           |
| M8      | M6     | curve residual and noise copy | w300     |      4 | 47.000 |       0.760 |        0.240 | True           |
| M8      | M6     | curve residual and noise copy | w300     |      5 | 46.000 |       0.336 |        0.537 | False          |
| M8      | M6     | curve residual and noise copy | w300     |      6 | 46.000 |       0.515 |        0.241 | True           |
| M8      | M6     | curve residual and noise copy | w300     |      7 | 77.000 |       0.754 |        0.194 | True           |
| M8      | M6     | curve residual and noise copy | w300     |      8 | 76.000 |       0.185 |        0.207 | False          |
| M8      | M6     | curve residual and noise copy | w400     |      1 | 78.000 |       0.235 |        0.138 | True           |
| M8      | M6     | curve residual and noise copy | w400     |      2 | 73.000 |       0.342 |        0.347 | False          |
| M8      | M6     | curve residual and noise copy | w400     |      3 | 76.000 |       0.221 |        0.106 | True           |
| M8      | M6     | curve residual and noise copy | w400     |      4 | 47.000 |       0.559 |        0.194 | True           |
| M8      | M6     | curve residual and noise copy | w400     |      5 | 46.000 |       0.517 |        0.328 | True           |
| M8      | M6     | curve residual and noise copy | w400     |      6 | 46.000 |       0.433 |        0.364 | True           |
| M8      | M6     | curve residual and noise copy | w400     |      7 | 77.000 |       0.358 |        0.189 | True           |
| M8      | M6     | curve residual and noise copy | w400     |      8 | 76.000 |       0.225 |        0.117 | True           |
| M8      | M4     | curve instead of IC peak      | any      |      1 | 78.000 |       0.181 |        0.138 | True           |
| M8      | M4     | curve instead of IC peak      | any      |      2 | 73.000 |       0.400 |        0.347 | True           |
| M8      | M4     | curve instead of IC peak      | any      |      3 | 76.000 |       0.208 |        0.106 | True           |
| M8      | M4     | curve instead of IC peak      | any      |      4 | 47.000 |       0.326 |        0.194 | True           |
| M8      | M4     | curve instead of IC peak      | any      |      5 | 46.000 |       0.436 |        0.328 | True           |
| M8      | M4     | curve instead of IC peak      | any      |      6 | 46.000 |       0.297 |        0.364 | False          |
| M8      | M4     | curve instead of IC peak      | any      |      7 | 77.000 |       0.388 |        0.189 | True           |
| M8      | M4     | curve instead of IC peak      | any      |      8 | 76.000 |       0.152 |        0.117 | True           |
| M8      | M4     | curve instead of IC peak      | w200     |      1 | 78.000 |       0.237 |        0.291 | False          |
| M8      | M4     | curve instead of IC peak      | w200     |      2 | 73.000 |       0.570 |        0.609 | False          |
| M8      | M4     | curve instead of IC peak      | w200     |      3 | 76.000 |       0.269 |        0.215 | True           |
| M8      | M4     | curve instead of IC peak      | w200     |      4 | 47.000 |       0.381 |        0.305 | True           |
| M8      | M4     | curve instead of IC peak      | w200     |      5 | 46.000 |       0.358 |        0.580 | False          |
| M8      | M4     | curve instead of IC peak      | w200     |      6 | 46.000 |       0.282 |        0.466 | False          |
| M8      | M4     | curve instead of IC peak      | w200     |      7 | 77.000 |       0.580 |        0.345 | True           |
| M8      | M4     | curve instead of IC peak      | w200     |      8 | 76.000 |       0.197 |        0.255 | False          |
| M8      | M4     | curve instead of IC peak      | w300     |      1 | 78.000 |       0.219 |        0.178 | True           |
| M8      | M4     | curve instead of IC peak      | w300     |      2 | 73.000 |       0.509 |        0.539 | False          |
| M8      | M4     | curve instead of IC peak      | w300     |      3 | 76.000 |       0.243 |        0.159 | True           |
| M8      | M4     | curve instead of IC peak      | w300     |      4 | 47.000 |       0.356 |        0.240 | True           |
| M8      | M4     | curve instead of IC peak      | w300     |      5 | 46.000 |       0.372 |        0.537 | False          |
| M8      | M4     | curve instead of IC peak      | w300     |      6 | 46.000 |       0.291 |        0.241 | True           |
| M8      | M4     | curve instead of IC peak      | w300     |      7 | 77.000 |       0.455 |        0.194 | True           |
| M8      | M4     | curve instead of IC peak      | w300     |      8 | 76.000 |       0.165 |        0.207 | False          |
| M8      | M4     | curve instead of IC peak      | w400     |      1 | 78.000 |       0.181 |        0.138 | True           |
| M8      | M4     | curve instead of IC peak      | w400     |      2 | 73.000 |       0.400 |        0.347 | True           |
| M8      | M4     | curve instead of IC peak      | w400     |      3 | 76.000 |       0.208 |        0.106 | True           |
| M8      | M4     | curve instead of IC peak      | w400     |      4 | 47.000 |       0.326 |        0.194 | True           |
| M8      | M4     | curve instead of IC peak      | w400     |      5 | 46.000 |       0.436 |        0.328 | True           |
| M8      | M4     | curve instead of IC peak      | w400     |      6 | 46.000 |       0.297 |        0.364 | False          |
| M8      | M4     | curve instead of IC peak      | w400     |      7 | 77.000 |       0.388 |        0.189 | True           |
| M8      | M4     | curve instead of IC peak      | w400     |      8 | 76.000 |       0.152 |        0.117 | True           |
