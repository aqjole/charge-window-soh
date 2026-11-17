/*
 * Streaming partial-charge SOH estimator: M1 (capacity = a + b * dq) or M6
 * (Gaussian-process mean on the two half-window charges dq_a, dq_b).
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
 *   - the same accumulation at the midpoint level (V1 + V2) / 2 gives tm, and
 *     dq_a = current * (tm - t1) / 3600, dq_b = current * (t2 - tm) / 3600.
 *
 * Three accumulators and the previous sample: no buffer, no heap. C99, double.
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

/* GPR predictive mean (Matern 5/2 kernel) on x = (dq_a, dq_b) [mAh], as fitted by
 * the Python reference (src/soh/models.py) and exported by src/soh/freeze.py:
 *   z   = ((x - x_mean) / x_scale) / length_scale
 *   r_i = sqrt(5) * |z - z_train_i|
 *   capacity = y_std * sum_i amplitude * (1 + r_i + r_i^2 / 3) * exp(-r_i) * alpha_i + y_mean
 * The arrays live in the generated model header (const, no heap). */
typedef struct {
    int n_train;
    double x_mean[2], x_scale[2], length_scale[2];
    double amplitude;
    double y_mean, y_std;  /* mAh */
    const double *z_train; /* 2 * n_train, row-major */
    const double *alpha;   /* n_train */
} soh_gpr;

double soh_gpr_predict(const soh_gpr *m, double dq_a_mAh, double dq_b_mAh);

typedef struct {
    double v1_mV, v2_mV;   /* window levels */
    double arm_band_mV;    /* arming: v < v1 - arm_band */
    double end_band_mV;    /* done: v >= v2 + end_band */
    double current_mA;     /* assumed constant charge current */
    double max_gap_s;      /* longest allowed sample gap inside the window */
    double a_mAh, b;       /* capacity [mAh] = a + b * dq [mAh] */
    double c0_mAh;         /* beginning-of-life capacity, for SOH */
    const soh_gpr *gpr;    /* NULL: M1 with a and b; otherwise M6, a and b unused */
} soh_config;

typedef struct {
    soh_config cfg;
    soh_status status;
    int armed, gap;
    double t_arm, t_prev, v_prev;
    double vm_mV;              /* midpoint level (V1 + V2) / 2 */
    double below1_s, below2_s, belowm_s; /* time below V1, V2 and the midpoint since arming */
    double dq_mAh, dq_a_mAh, dq_b_mAh, capacity_mAh, soh; /* valid when status == SOH_OK */
} soh_est;

void soh_est_init(soh_est *e, const soh_config *cfg);

/* One sample. Returns SOH_RUNNING until the window completes; afterwards
 * further samples are ignored and the final status is returned. */
soh_status soh_est_feed(soh_est *e, double t_s, double v_mV);

/* End of trace: turns a still-running estimate into NOT_ARMED or NO_V2. */
soh_status soh_est_finish(soh_est *e);

const char *soh_status_name(soh_status s);

#endif
