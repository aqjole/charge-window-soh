# Degraded-log tests: mean of 5 charges

Mean estimate over 5 charges against the single-charge estimate, for the cases with random noise or sampling phase (main detector). The 20 seeds of a case are independent logs of the same charge; they are split into blocks of 5 and each block's answered estimates are averaged, as a BMS could do over consecutive charges. Both sides are scored on the charges the model answered; empty where it answered none. worst_cell is the highest per-cell RMSE. The 7-of-8-cells rule is not applied: a mean cannot have a higher RMSE than its members, so it would pass by construction, and only the size of the gain is informative. Not covered: errors that repeat from charge to charge (a constant offset), and the dataset has no consecutive charges, so the repeats are simulated.

| case        | model   |   n_charges |   n_blocks |   rmse_single |   rmse_avg |   worst_cell_single |   worst_cell_avg |   max_abs_single |   max_abs_avg |
|:------------|:--------|------------:|-----------:|--------------:|-----------:|--------------------:|-----------------:|-----------------:|--------------:|
| noise 1 mV  | M1      |           5 |          4 |         0.680 |      0.671 |               1.153 |            1.152 |            7.529 |         7.481 |
| noise 1 mV  | M2      |           5 |          4 |         0.509 |      0.502 |               1.113 |            1.111 |            7.189 |         7.131 |
| noise 1 mV  | M3      |           5 |          4 |         0.461 |      0.456 |               0.656 |            0.654 |            3.975 |         3.760 |
| noise 1 mV  | M4      |           5 |          4 |         0.342 |      0.303 |               0.474 |            0.455 |            2.445 |         2.241 |
| noise 1 mV  | M5      |           5 |          4 |         0.419 |      0.408 |               0.837 |            0.826 |            5.674 |         5.025 |
| noise 1 mV  | M6      |           5 |          4 |         0.433 |      0.424 |               0.707 |            0.697 |            3.417 |         3.211 |
| noise 1 mV  | M8      |           5 |          4 |         0.272 |      0.235 |               0.387 |            0.358 |            2.094 |         1.934 |
| noise 2 mV  | M1      |           5 |          4 |         0.686 |      0.669 |               1.153 |            1.151 |            7.541 |         7.476 |
| noise 2 mV  | M2      |           5 |          4 |         0.525 |      0.511 |               1.144 |            1.139 |            7.261 |         7.157 |
| noise 2 mV  | M3      |           5 |          4 |         0.464 |      0.455 |               0.658 |            0.654 |            4.170 |         3.723 |
| noise 2 mV  | M4      |           5 |          4 |         0.416 |      0.349 |               0.586 |            0.549 |            2.649 |         2.212 |
| noise 2 mV  | M5      |           5 |          4 |         0.430 |      0.408 |               0.834 |            0.811 |            5.859 |         4.901 |
| noise 2 mV  | M6      |           5 |          4 |         0.443 |      0.425 |               0.712 |            0.693 |            3.491 |         3.253 |
| noise 2 mV  | M8      |           5 |          4 |         0.308 |      0.245 |               0.415 |            0.363 |            2.144 |         1.907 |
| noise 5 mV  | M1      |           5 |          4 |         0.706 |      0.665 |               1.152 |            1.147 |            7.610 |         7.452 |
| noise 5 mV  | M2      |           5 |          4 |         0.788 |      0.759 |               1.453 |            1.440 |            7.566 |         7.379 |
| noise 5 mV  | M3      |           5 |          4 |         0.476 |      0.453 |               0.664 |            0.651 |            4.042 |         3.677 |
| noise 5 mV  | M4      |           5 |          4 |         1.038 |      0.955 |               1.299 |            1.249 |            4.611 |         3.679 |
| noise 5 mV  | M5      |           5 |          4 |         0.469 |      0.419 |               0.873 |            0.819 |            5.622 |         4.614 |
| noise 5 mV  | M6      |           5 |          4 |         0.474 |      0.431 |               0.729 |            0.682 |            3.753 |         3.258 |
| noise 5 mV  | M8      |           5 |          4 |         0.385 |      0.270 |               0.482 |            0.389 |            2.122 |         1.961 |
| noise 10 mV | M1      |           5 |          4 |         0.837 |      0.752 |               1.172 |            1.153 |            7.539 |         7.364 |
| noise 10 mV | M2      |           5 |          4 |         1.556 |      1.520 |               2.298 |            2.279 |            7.586 |         7.239 |
| noise 10 mV | M3      |           5 |          4 |         0.541 |      0.476 |               0.753 |            0.720 |            4.330 |         3.565 |
| noise 10 mV | M4      |           5 |          4 |         2.334 |      2.246 |               2.762 |            2.701 |            8.595 |         7.727 |
| noise 10 mV | M5      |           5 |          4 |         0.671 |      0.581 |               1.191 |            1.088 |            6.835 |         4.854 |
| noise 10 mV | M6      |           5 |          4 |         0.583 |      0.481 |               0.813 |            0.714 |            3.907 |         3.098 |
| noise 10 mV | M8      |           5 |          4 |         0.545 |      0.410 |               0.673 |            0.601 |            2.708 |         1.907 |
| period 10 s | M1      |           5 |          4 |         0.672 |      0.672 |               1.153 |            1.153 |            7.500 |         7.480 |
| period 10 s | M2      |           5 |          4 |         0.511 |      0.503 |               1.104 |            1.101 |            7.226 |         7.160 |
| period 10 s | M3      |           5 |          4 |         0.456 |      0.455 |               0.652 |            0.652 |            3.827 |         3.744 |
| period 10 s | M4      |           5 |          4 |         0.373 |      0.316 |               0.475 |            0.433 |            2.531 |         2.369 |
| period 10 s | M5      |           5 |          4 |         0.405 |      0.404 |               0.820 |            0.818 |            5.094 |         4.944 |
| period 10 s | M6      |           5 |          4 |         0.423 |      0.422 |               0.698 |            0.697 |            3.198 |         3.157 |
| period 10 s | M8      |           5 |          4 |         0.230 |      0.226 |               0.359 |            0.356 |            1.906 |         1.882 |
| period 30 s | M1      |           5 |          4 |         0.672 |      0.670 |               1.153 |            1.152 |            7.479 |         7.469 |
| period 30 s | M2      |           5 |          4 |         0.570 |      0.518 |               1.137 |            1.115 |            7.761 |         7.498 |
| period 30 s | M3      |           5 |          4 |         0.454 |      0.454 |               0.639 |            0.639 |            3.818 |         3.737 |
| period 30 s | M4      |           5 |          4 |         0.662 |      0.441 |               0.789 |            0.576 |            4.316 |         2.551 |
| period 30 s | M5      |           5 |          4 |         0.411 |      0.409 |               0.835 |            0.833 |            5.169 |         5.073 |
| period 30 s | M6      |           5 |          4 |         0.422 |      0.421 |               0.694 |            0.693 |            3.215 |         3.144 |
| period 30 s | M8      |           5 |          4 |         0.230 |      0.225 |               0.373 |            0.370 |            1.904 |         1.860 |
| period 60 s | M1      |           5 |          4 |         0.670 |      0.669 |               1.152 |            1.152 |            7.464 |         7.417 |
| period 60 s | M2      |           5 |          4 |       nan     |    nan     |             nan     |          nan     |          nan     |       nan     |
| period 60 s | M3      |           5 |          4 |         0.453 |      0.452 |               0.636 |            0.635 |            3.763 |         3.697 |
| period 60 s | M4      |           5 |          4 |       nan     |    nan     |             nan     |          nan     |          nan     |       nan     |
| period 60 s | M5      |           5 |          4 |         0.419 |      0.417 |               0.840 |            0.838 |            5.111 |         4.925 |
| period 60 s | M6      |           5 |          4 |         0.423 |      0.421 |               0.686 |            0.685 |            3.247 |         3.141 |
| period 60 s | M8      |           5 |          4 |         0.255 |      0.243 |               0.414 |            0.406 |            1.835 |         1.784 |
| combined    | M1      |           5 |          4 |         0.843 |      0.706 |               1.158 |            1.139 |            7.745 |         7.466 |
| combined    | M2      |           5 |          4 |         0.633 |      0.543 |               1.181 |            1.140 |            7.743 |         7.482 |
| combined    | M3      |           5 |          4 |         0.555 |      0.481 |               0.870 |            0.699 |            5.004 |         4.249 |
| combined    | M4      |           5 |          4 |         0.806 |      0.538 |               0.918 |            0.708 |            4.108 |         2.985 |
| combined    | M5      |           5 |          4 |         0.593 |      0.437 |               0.932 |            0.769 |            7.264 |         5.020 |
| combined    | M6      |           5 |          4 |         0.585 |      0.457 |               0.877 |            0.708 |            4.292 |         3.214 |
| combined    | M8      |           5 |          4 |         0.565 |      0.365 |               0.630 |            0.469 |            2.993 |         2.284 |
