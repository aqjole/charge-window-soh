/*
 * Host replay: stream exported traces through the C estimator.
 *
 *   replay [v1_mV v2_mV a_mAh b] < traces.csv > estimates.csv
 *
 * Input:  header, then rows  cell,cycle,c0_mah,t_s,v_mV  (one trace = consecutive
 *         rows with the same cell and cycle), as written by `python -m soh.export`.
 * Output: header, then one row per trace  cell,cycle,reason,dq_mah,capacity_mah,soh
 *         (the last three empty unless reason is OK).
 * Without arguments the frozen configuration from soh_model.h is used; the four
 * optional arguments override the window and coefficients (used by the tests).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "soh_est.h"
#include "soh_model.h"

#define LINE_MAX_LEN 256

static void emit(long cell, long cycle, soh_est *e)
{
    soh_status s = soh_est_finish(e);
    if (s == SOH_OK) {
        printf("%ld,%ld,%s,%.17g,%.17g,%.17g\n", cell, cycle, soh_status_name(s), e->dq_mAh, e->capacity_mAh, e->soh);
    } else {
        printf("%ld,%ld,%s,,,\n", cell, cycle, soh_status_name(s));
    }
}

static int parse_row(char *line, long *cell, long *cycle, double *c0, double *t, double *v)
{
    char *p = line, *end;
    *cell = strtol(p, &end, 10);
    if (end == p || *end != ',') return 0;
    p = end + 1;
    *cycle = strtol(p, &end, 10);
    if (end == p || *end != ',') return 0;
    p = end + 1;
    *c0 = strtod(p, &end);
    if (end == p || *end != ',') return 0;
    p = end + 1;
    *t = strtod(p, &end);
    if (end == p || *end != ',') return 0;
    p = end + 1;
    *v = strtod(p, &end);
    if (end == p) return 0;
    return 1;
}

int main(int argc, char **argv)
{
    soh_config cfg = {
        SOH_MODEL_V1_MV, SOH_MODEL_V2_MV, SOH_MODEL_ARM_BAND_MV, SOH_MODEL_END_BAND_MV,
        SOH_MODEL_CURRENT_MA, SOH_MODEL_MAX_GAP_S, SOH_MODEL_A_MAH, SOH_MODEL_B, 0.0,
    };
    soh_est est;
    char line[LINE_MAX_LEN];
    long cell = 0, cycle = 0, cur_cell = 0, cur_cycle = 0, lineno = 0;
    double c0, t, v;
    int open = 0;

    if (argc == 5) {
        cfg.v1_mV = strtod(argv[1], NULL);
        cfg.v2_mV = strtod(argv[2], NULL);
        cfg.a_mAh = strtod(argv[3], NULL);
        cfg.b = strtod(argv[4], NULL);
    } else if (argc != 1) {
        fprintf(stderr, "usage: %s [v1_mV v2_mV a_mAh b] < traces.csv\n", argv[0]);
        return 2;
    }

    if (!fgets(line, sizeof line, stdin)) {
        fprintf(stderr, "empty input\n");
        return 1;
    }
    printf("cell,cycle,reason,dq_mah,capacity_mah,soh\n");
    while (fgets(line, sizeof line, stdin)) {
        lineno++;
        if (!parse_row(line, &cell, &cycle, &c0, &t, &v)) {
            fprintf(stderr, "bad row %ld: %s", lineno + 1, line);
            return 1;
        }
        if (!open || cell != cur_cell || cycle != cur_cycle) {
            if (open) emit(cur_cell, cur_cycle, &est);
            cfg.c0_mAh = c0;
            soh_est_init(&est, &cfg);
            cur_cell = cell;
            cur_cycle = cycle;
            open = 1;
        }
        soh_est_feed(&est, t, v);
    }
    if (open) emit(cur_cell, cur_cycle, &est);
    return 0;
}
