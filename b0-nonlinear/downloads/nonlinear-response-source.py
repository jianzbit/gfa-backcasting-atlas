"""Low-rank asymmetric responses inside B0, with a crossed input-policy control.

This is not a causal COVID/war model. The two hinges respond to qualified pooled
annual departures. An absent signal is not a measured zero. All calibration is
label-free, country-balanced, historical and confined to the training countries.
"""
from __future__ import annotations
import copy
import numpy as np
import pandas as pd
from v7 import shared_dynamic_stock as b0
from v7 import observed_driver_extension as observed

AXES = {"activity": 4, "demand_shock": 5}
RIDGE = np.r_[b0.RIDGE, 9., 9.]
NAMES = b0.COEFFICIENTS + ["activity_negative_departure_hinge", "demand_negative_departure_hinge"]


def operator(panel, model):
    policy = model.get("input_policy", "legacy")
    if policy == "observed":
        states, usage, coords, diagnostics, extension = observed.encode_panel(panel, model)
    elif policy == "legacy":
        states, usage, coords, diagnostics = b0.encode_panel(panel, model, excluded_donors=model.get("excluded_countries", []))
        extension = pd.DataFrame()
    else:
        raise ValueError("Unknown input policy")
    hist = b0.historical_source_view(panel)
    inputs = {}
    for c, state in states.items():
        g = hist.loc[hist.country_id.eq(c)].sort_values("year")
        used = usage.loc[usage.country_id.eq(c)]
        inputs[c] = {}
        for axis, ix in AXES.items():
            names = used.loc[used.family.isin(b0.TIMING_AXES[axis]) & used.used_for_annual_timing, "factor_name"].tolist()
            support = np.isfinite(g[names].to_numpy(float)).any(axis=1) if names else np.zeros(5, bool)
            mask = np.r_[support, np.repeat(support[-3:].any(), 10)]
            roles = np.repeat("historical_qualified_or_proxy_departure", 15).astype(object)
            roles[5:] = "damped_historical_departure_not_observed_shock"
            if policy == "observed":
                ex = extension.loc[extension.country_id.eq(c) & extension.axis.eq(axis)].sort_values("interval_end_year")
                for r in ex.to_dict("records"):
                    j = int(r["interval_end_year"]) - 2016
                    roles[j] = r["extension_role"]
                    # The continuation is a model state, not an observed zero.
                    if r["extension_role"] != "unchanged_v16_damped_historical_axis_no_qualified_new_source":
                        mask[j] = True
            inputs[c][axis] = (state["zr"][:, ix] / b0.RATE_SCALE, mask, roles)
    return states, usage, coords, diagnostics, extension, inputs


def calibrate(inputs, countries):
    result = {}
    for axis in AXES:
        values, weights, supported = [], [], []
        for c in countries:
            x, mask, _ = inputs[c][axis]
            ok = mask[:5] & np.isfinite(x[:5])
            if ok.sum() < 3:
                continue
            supported.append(c); values.extend(x[:5][ok]); weights.extend([1 / ok.sum()] * ok.sum())
        x, w = np.asarray(values), np.asarray(weights)
        p = dict(enabled=False, training_support_countries=supported, calibration_rows=len(x),
                 knot=0., label_free=True, calibration_window="2016–2020", disabled_reason="insufficient_two_sided_support")
        if len(supported) >= 3 and (x < -1e-8).any() and (x > 1e-8).any():
            w = w / w.sum()
            # No intercept projection: zero departure must yield zero added rate.
            projection = float(np.sum(w * x * np.maximum(-x, 0)) / np.sum(w * x*x))
            residual = np.maximum(-x, 0) - projection*x
            scale = float(np.sqrt(np.sum(w * residual**2)))
            if scale > 1e-10:
                p.update(enabled=True, projection=projection, residual_rms=scale,
                         lower=float(x.min()), upper=float(x.max()), disabled_reason=None)
        result[axis] = p
    return result


def basis(values, support, p):
    x = np.asarray(values, float); support = np.asarray(support, bool)
    out = np.zeros(len(x)); used = support & np.isfinite(x) & p["enabled"]
    outside = np.zeros(len(x), bool)
    if used.any():
        outside[used] = (x[used] < p["lower"] - 1e-12) | (x[used] > p["upper"] + 1e-12)
        # Bounded added response; the unchanged linear term retains its policy.
        z = np.clip(x[used], p["lower"], p["upper"])
        out[used] = (np.maximum(-z, 0) - p["projection"]*z) / p["residual_rms"]
    return out, used, outside


def augment(states, inputs, parameters):
    states = copy.deepcopy(states); rows = []
    for c, s in states.items():
        columns = []
        for axis in AXES:
            x, support, roles = inputs[c][axis]
            value, used, outside = basis(x, support, parameters[axis])
            columns.append(b0.RATE_SCALE*value)
            for j, y in enumerate(b0.RATE_YEARS):
                rows.append(dict(country_id=c, year=int(y), axis=axis, departure=float(x[j]),
                                 basis_value=float(value[j]), term_used=bool(used[j]),
                                 outside_training_input_range=bool(outside[j]), source_role=roles[j],
                                 observed_zero_imputed=False))
        cumulative = b0.cumulative_operator(np.column_stack(columns))
        for k in ["br", "bn"]:
            s[k] = np.column_stack([s[k], cumulative])
    return states, pd.DataFrame(rows)


def objective(theta, states, blocks, derivatives=False):
    value = .5*float((RIDGE*theta)@theta)
    grad, normal = RIDGE*theta, np.diag(RIDGE)
    for c, members, precision in blocks:
        pred = [b0.observation_logratio(states[c], theta, r["sector"], r["year"]) for r in members]
        residual = (np.array([v for v, _ in pred])-np.array([r["native_log_ratio_to_2020"] for r in members]))/b0.OBSERVATION_SCALE
        jac = np.stack([j for _, j in pred])/b0.OBSERVATION_SCALE
        norm = float(np.sqrt(max(0., residual@precision@residual)))
        robust = min(1., 1.35/norm) if norm else 1.
        value += .5*norm**2 if norm <= 1.35 else 1.35*(norm-.675)
        grad += robust*jac.T@precision@residual
        normal += robust*jac.T@precision@jac
    return (value, grad, normal) if derivatives else value


def fit(panel, observations, qualities, *, policy, nonlinear, excluded=()):
    if policy not in {"legacy", "observed"}:
        raise ValueError("Unknown policy")
    engine = observed if policy == "observed" else b0
    control, *_ = engine.fit_model(panel, observations, qualities, excluded_countries=excluded)
    model = copy.deepcopy(control)
    model.update(input_policy=policy, nonlinear_enabled=bool(nonlinear),
                 experiment="B0_asymmetric_annual_response_20261030", country_specific_parameters=False)
    states, usage, coords, diagnostics, extension, inputs = operator(panel, model)
    obs = observations.loc[~observations.country_id.isin(excluded) & observations.relative_change_training_eligible.map(b0.flag)].copy()
    blocks, budget = b0.training_blocks(obs, states)
    if not nonlinear:
        theta = np.asarray(model["coefficients"])
        _, _, normal = b0.objective(theta, states, blocks, True)
        model["local_working_edf"] = float(np.trace(np.linalg.solve(normal, normal-np.diag(b0.RIDGE))))
        return model, usage, coords, diagnostics, extension, pd.DataFrame(), budget
    parameters = calibrate(inputs, model["training_countries"])
    states, support = augment(states, inputs, parameters)
    theta = np.r_[control["coefficients"], 0., 0.]
    for iteration in range(600):
        value, grad, normal = objective(theta, states, blocks, True)
        if np.max(abs(grad)) < 1e-9:
            break
        step = np.linalg.solve(normal, -grad); scale = 1.
        while scale > 2**-30 and objective(theta+scale*step, states, blocks) > value+1e-4*scale*(grad@step):
            scale /= 2
        updated = theta+scale*step
        if np.max(abs(updated-theta)) < 1e-12:
            theta = updated; break
        theta = updated
    value, grad, normal = objective(theta, states, blocks, True)
    if not np.isfinite(theta).all() or np.max(abs(grad)) >= 1e-7:
        raise RuntimeError("Nonlinear optimizer not stationary")
    model.update(version="B0_"+policy+"_hinge", coefficients=theta.tolist(), coefficient_names=NAMES,
                 coefficients_count=9, nonlinear_basis=parameters, ridge=RIDGE.tolist(),
                 optimizer_iterations=iteration+1, objective=float(value), converged=True,
                 gradient_inf_norm=float(np.max(abs(grad))),
                 local_working_edf=float(np.trace(np.linalg.solve(normal, normal-np.diag(RIDGE)))))
    return model, usage, coords, diagnostics, extension, support, budget


def predict(panel, model):
    linear = copy.deepcopy(model); linear["coefficients"] = model["coefficients"][:7]
    engine = observed if model["input_policy"] == "observed" else b0
    pred = engine.predict_model(panel, linear)[0]
    states, usage, coords, diagnostics, extension, inputs = operator(panel, model)
    support = pd.DataFrame()
    if model["nonlinear_enabled"]:
        states, support = augment(states, inputs, model["nonlinear_basis"])
        for c, g in pred.groupby("country_id", sort=False):
            g = g.sort_values("year"); s = states[c]
            correction = s["br"][:, 7:]@np.asarray(model["coefficients"][7:])
            if not np.isfinite(correction).all() or abs(correction).max() > 40:
                raise ValueError("Unsupported extreme correction")
            for col in ["residential_gfa_m2", "non_residential_gfa_m2", "total_gfa_m2"]:
                pred.loc[g.index, col] = g[col].to_numpy()*np.exp(correction)
            pred.loc[g.index, "nonlinear_cumulative_log_correction"] = correction
    for c, g in pred.groupby("country_id", sort=False):
        g = g.sort_values("year")
        for sector in ["residential", "non_residential", "total"]:
            v = pred.loc[g.index, sector+"_gfa_m2"]
            anchor = v[g.year.eq(2020)].iloc[0]
            pred.loc[g.index, sector+"_ratio_to_2020"] = v/anchor if anchor > 0 else np.nan
            pred.loc[g.index, sector+"_annual_net_change_m2"] = v.diff()
        pred.loc[g.index, "total_annual_growth_percent"] = 100*pred.loc[g.index, "total_gfa_m2"].pct_change(fill_method=None)
    pred["accounting_residual_m2"] = pred.residential_gfa_m2+pred.non_residential_gfa_m2-pred.total_gfa_m2
    pred["model_version"] = "B0_"+model["input_policy"]+("_hinge" if model["nonlinear_enabled"] else "_linear")
    pred["annual_growth_over10percent_flag"] = pred.total_annual_growth_percent.abs().gt(10)
    return pred, support, extension
