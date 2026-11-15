# C estimator agreement

C estimator (`c/soh_est.c`, via `build/replay`) against the Python reference on the same exported CSV (`%.9g`), frozen M1 at 3.8-4.0 V. Gate: identical reason codes on every trace and |SOH difference| <= 0.0001 on every answered trace. Differences are shown as a power-of-ten upper bound; SOH is a fraction (1e-4 = 0.01 SOH points).

| case           |   n_traces |   n_OK |   n_NOT_ARMED |   n_NO_V2 |   n_GAP |   missing_traces |   reason_mismatches | max_abs_diff_soh   | max_abs_diff_dq_mah   | passed   |
|:---------------|-----------:|-------:|--------------:|----------:|--------:|-----------------:|--------------------:|:-------------------|:----------------------|:---------|
| clean          |        519 |    519 |             0 |         0 |       0 |                0 |                   0 | < 1e-14            | < 1e-11               | yes      |
| combined_seed0 |        519 |    519 |             0 |         0 |       0 |                0 |                   0 | < 1e-14            | < 1e-12               | yes      |
