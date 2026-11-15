/*
 * Streaming partial-charge SOH estimator (M1: capacity = a + b * dq).
 *
 * Feed one charge trace sample by sample. The window detector is the
 * time-below-level rule of the Python reference (src/soh/features.py):
 *
 *   - armed at the first sample with v < V1 - arm band;
 *   - done at the first later sample with v >= V2 + end band;
 *   - between consecutive samples the voltage is taken as linear, and the time
 *     spent below V1 and below V2 is accumulated;
 *   - t1 = t_arm + time below V1, t2 = t_arm + time below V2,
 *     dq = current * (t2 - t1) / 3600;
 *   - GAP if a segment that contributes window time is longer than max gap.
 *
 * Two accumulators and the previous sample: no buffer, no heap. C99, double.
 * Current is assumed constant at current_mA, as in the Python reference.
 */
#ifndef SOH_EST_H
#define SOH_EST_H

typedef enum {
    SOH_RUNNING = 0, /* more samples needed */
    SOH_OK,          /* window complete, result valid */
    SOH_NOT_ARMED,   /* trace ended without a sample below V1 - arm band */
    SOH_NO_V2,       /* trace ended before V2 + end band was reached */
    SOH_GAP          /* a sample gap above max gap inside the window */
} soh_status;

typedef struct {
    double v1_mV, v2_mV;   /* window levels */
    double arm_band_mV;    /* arming: v < v1 - arm_band */
    double end_band_mV;    /* done: v >= v2 + end_band */
    double current_mA;     /* assumed constant charge current */
    double max_gap_s;      /* longest allowed sample gap inside the window */
    double a_mAh, b;       /* capacity [mAh] = a + b * dq [mAh] */
    double c0_mAh;         /* beginning-of-life capacity, for SOH */
} soh_config;

typedef struct {
    soh_config cfg;
    soh_status status;
    int armed, gap;
    double t_arm, t_prev, v_prev;
    double below1_s, below2_s; /* time below V1 and V2 since arming */
    double dq_mAh, capacity_mAh, soh; /* valid when status == SOH_OK */
} soh_est;

void soh_est_init(soh_est *e, const soh_config *cfg);

/* One sample. Returns SOH_RUNNING until the window completes; afterwards
 * further samples are ignored and the final status is returned. */
soh_status soh_est_feed(soh_est *e, double t_s, double v_mV);

/* End of trace: turns a still-running estimate into NOT_ARMED or NO_V2. */
soh_status soh_est_finish(soh_est *e);

const char *soh_status_name(soh_status s);

#endif
