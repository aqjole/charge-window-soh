#include "soh_est.h"

/* Time the linearly interpolated voltage spends below `level` on one segment.
 * Same case split and expressions as `time_below` in src/soh/features.py. */
static double time_below(double a, double b, double level, double dt)
{
    double frac = 0.0;
    if (a < level && b < level) {
        frac = 1.0;
    } else if (a < level && b >= level) {
        frac = (level - a) / (b - a);
    } else if (a >= level && b < level) {
        frac = (level - b) / (a - b);
    }
    return frac * dt;
}

void soh_est_init(soh_est *e, const soh_config *cfg)
{
    e->cfg = *cfg;
    e->status = SOH_RUNNING;
    e->armed = 0;
    e->gap = 0;
    e->t_arm = e->t_prev = e->v_prev = 0.0;
    e->below1_s = e->below2_s = 0.0;
    e->dq_mAh = e->capacity_mAh = e->soh = 0.0;
}

soh_status soh_est_feed(soh_est *e, double t_s, double v_mV)
{
    const soh_config *c = &e->cfg;
    double dt, b1, b2, t1, t2;

    if (e->status != SOH_RUNNING) {
        return e->status;
    }
    if (!e->armed) {
        if (v_mV < c->v1_mV - c->arm_band_mV) {
            e->armed = 1;
            e->t_arm = e->t_prev = t_s;
            e->v_prev = v_mV;
        }
        return SOH_RUNNING;
    }

    dt = t_s - e->t_prev;
    b1 = time_below(e->v_prev, v_mV, c->v1_mV, dt);
    b2 = time_below(e->v_prev, v_mV, c->v2_mV, dt);
    if (b2 - b1 > 0.0 && dt > c->max_gap_s) {
        e->gap = 1;
    }
    e->below1_s += b1;
    e->below2_s += b2;
    e->t_prev = t_s;
    e->v_prev = v_mV;

    if (v_mV >= c->v2_mV + c->end_band_mV) {
        if (e->gap) {
            e->status = SOH_GAP;
        } else {
            t1 = e->t_arm + e->below1_s;
            t2 = e->t_arm + e->below2_s;
            e->dq_mAh = c->current_mA * (t2 - t1) / 3600.0;
            e->capacity_mAh = c->a_mAh + c->b * e->dq_mAh;
            e->soh = e->capacity_mAh / c->c0_mAh;
            e->status = SOH_OK;
        }
    }
    return e->status;
}

soh_status soh_est_finish(soh_est *e)
{
    if (e->status == SOH_RUNNING) {
        e->status = e->armed ? SOH_NO_V2 : SOH_NOT_ARMED;
    }
    return e->status;
}

const char *soh_status_name(soh_status s)
{
    switch (s) {
    case SOH_RUNNING:
        return "RUNNING";
    case SOH_OK:
        return "OK";
    case SOH_NOT_ARMED:
        return "NOT_ARMED";
    case SOH_NO_V2:
        return "NO_V2";
    case SOH_GAP:
        return "GAP";
    }
    return "?";
}
