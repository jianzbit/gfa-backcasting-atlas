"""Seven-coefficient shared net-stock model, conditional on physical proxies.

Two states are integrated from a fixed2020Total. Native stock ratios have
separate observation channels; Total uses the nonlinear sum of component stocks.
No new-construction/demolition decomposition or legal-area conversion is fitted.
"""
from __future__ import annotations

import copy
import numpy as np
import pandas as pd

from v7.backcast_cumulative_timing import FAMILIES, STATIC, TOTAL_AXES, TIMING_AXES
from v7.backcast_observation_dynamic import QUALITY, FAMILY_WEIGHT, CONSTRUCTION, LAG, PIPELINE

YEARS = np.arange(2015, 2031)
RATE_YEARS = np.arange(2016, 2031)
RATE_SCALE = .01
OBSERVATION_SCALE = .05
FUTURE_DAMPING = .8
RIDGE = np.array([1., 1., 1., 1., 1., 1., 9.])
RESERVED = {"LVA", "NLD"}
OBAT_MORPH = ["obat_nonres_footprint_share", "obat_height_median_m", "obat_height_iqr_m", "obat_mean_footprint_area_m2"]
OBAT_AGE = ["obat_pre1980_footprint_share", "obat_2010_2020_footprint_share"]
ALL_STATIC = set(STATIC) | set(OBAT_MORPH + OBAT_AGE) | {"real_interest_rate_fraction"}
GROUPS = copy.deepcopy(FAMILIES)
GROUPS["morphology"] += OBAT_MORPH
GROUPS["stock_background"] += OBAT_AGE
COEFFICIENTS = ["shared_intercept", "demand_period_mean", "production_period_mean", "background_dynamic_interaction", "annual_activity_departure", "annual_demand_departure", "nonresidential_growth_departure"]


def flag(x):
    return x is True or isinstance(x, (bool, np.bool_)) and bool(x) or str(x).lower() == "true"


def mean_available(values, weights=None, length=1):
    if not values:
        return np.full(length, np.nan)
    a = np.asarray(values, float)
    w = np.ones(len(a)) if weights is None else np.asarray(weights, float)
    w = w[:, None]
    good = np.isfinite(a)
    den = (good * w).sum(axis=0)
    result = np.full(a.shape[1], np.nan)
    ok = den > 0
    result[ok] = np.where(good, a * w, 0.).sum(axis=0)[ok] / den[ok]
    return result


def historical_source_view(panel):
    """Leave source NaN unchanged; construct explicit distributed-lag views."""
    h = panel[panel.year.between(2016, 2020)].sort_values(["country_id", "year"]).copy()
    for name in {n for ns in GROUPS.values() for n in ns}:
        if name not in h:
            h[name] = np.nan
        q = name + "__qualified"
        if q in h:
            h[name] = pd.to_numeric(h[name], errors="raise").where(h[q].map(flag))
    a, b = h[CONSTRUCTION].to_numpy(float), h[LAG].to_numpy(float)
    h[CONSTRUCTION] = np.where(np.isfinite(a) & np.isfinite(b), (a + b) / 2, np.nan)
    for name in PIPELINE:
        prev = h.groupby("country_id")[name].shift(1).to_numpy(float)
        now = h[name].to_numpy(float)
        h[name] = np.where(np.isfinite(prev) & np.isfinite(now), (prev + now) / 2, np.nan)
    return h


def transformed(values, name):
    a = np.asarray(values, float).copy()
    if name == "obat_mean_footprint_area_m2":
        a = np.where(a >= 0, np.log1p(np.maximum(a, 0)), np.nan)
    if name in {"disaster_affected_per1000_population", "conflict_deaths_per1000_population"}:
        a = -a
    return a


def feature_parameters(view, countries, qualities, removed_groups=()):
    result = {}
    for family, names in GROUPS.items():
        for name in names:
            summaries, centered, supported = [], [], 0
            for c in countries:
                values = transformed(view[view.country_id.eq(c)][name].to_numpy(float), name)
                good = np.isfinite(values)
                if name in ALL_STATIC:
                    s = values[-1] if len(values) and np.isfinite(values[-1]) else np.nan
                else:
                    s = values[good].mean() if good.sum() >= 3 else np.nan
                summaries.append(s)
                if name not in ALL_STATIC and good.sum() >= 3:
                    centered.extend((values[good] - values[good].mean()).tolist())
                    supported += 1
            finite = np.asarray(summaries)[np.isfinite(summaries)]
            center = float(finite.mean()) if name in ALL_STATIC and len(finite) else 0.
            scale = float(np.sqrt(np.mean((finite - center) ** 2))) if len(finite) else 0.
            annual_scale = float(np.sqrt(np.mean(np.square(centered)))) if centered else 0.
            quality = QUALITY.get(qualities.get(name, "contextual_or_proxy_based"), 0.)
            allowed = family not in removed_groups and quality > 0 and name != LAG and not ("all_static" in removed_groups and name in ALL_STATIC)
            result[name] = dict(family=family, quality=quality, center=center, scale=scale or 1., annual_scale=annual_scale or 1.,
                cumulative_enabled=bool(allowed and len(finite) >= 3 and scale > 1e-12),
                annual_enabled=bool(allowed and name not in ALL_STATIC and supported >= 3 and annual_scale > 1e-12),
                min=float(finite.min()) if len(finite) else None, max=float(finite.max()) if len(finite) else None,
                support_countries=int(len(finite)), annual_support_countries=supported, static=name in ALL_STATIC)
    return result


def pool_family(values, family, length, qualities):
    """Common-source height/age variants receive one mechanism vote."""
    if family == "morphology":
        legacy_names = [n for n in values if not n.startswith("obat_")]
        legacy = mean_available([values[n] for n in legacy_names], [qualities[n] for n in legacy_names], length=length)
        height_names = [n for n in ["obat_height_median_m", "obat_height_iqr_m"] if n in values]
        height = mean_available([values[n] for n in height_names], [qualities[n] for n in height_names], length=length)
        obat = mean_available([values.get("obat_nonres_footprint_share", np.full(length, np.nan)), height,
            values.get("obat_mean_footprint_area_m2", np.full(length, np.nan))], length=length)
        return mean_available([legacy, obat], length=length)
    if family == "stock_background":
        legacy_names = [n for n in values if not n.startswith("obat_")]
        obat_names = [n for n in values if n.startswith("obat_")]
        legacy = mean_available([values[n] for n in legacy_names], [qualities[n] for n in legacy_names], length=length)
        obat = mean_available([-values[n] if n == "obat_2010_2020_footprint_share" else values[n] for n in obat_names], [qualities[n] for n in obat_names], length=length)
        return mean_available([legacy, obat], length=length)
    return mean_available(list(values.values()), [qualities[n] for n in values], length=length)


def smooth_partial(values):
    good = np.isfinite(values)
    out = np.full(5, np.nan)
    for j in np.flatnonzero(good):
        js = np.arange(max(0, j - 1), min(5, j + 2))
        keep = good[js]
        weights = np.where(js == j, 2., 1.)[keep]
        out[j] = np.average(values[js[keep]], weights=weights)
    if good.any():
        out[good] -= out[good].mean()
    return out


def encode_country(g, parameters):
    cumulative, annual, usage, outside, extra_background = {}, {}, [], False, []
    for family, names in GROUPS.items():
        totals, timing = {}, {}
        for name in names:
            p = parameters[name]
            raw = transformed(g[name].to_numpy(float), name)
            good = np.isfinite(raw)
            s = raw[-1] if p["static"] and good[-1] else raw[good].mean() if not p["static"] and good.sum() >= 3 else np.nan
            use_total = p["cumulative_enabled"] and np.isfinite(s)
            use_annual = p["annual_enabled"] and good.sum() >= 3
            if use_total:
                value = np.array([np.tanh((s - p["center"]) / p["scale"])])
                if p["static"] and family not in TOTAL_AXES["background"]:
                    extra_background.append(value)
                else:
                    totals[name] = value
                outside |= bool(s < p["min"] - 1e-12 or s > p["max"] + 1e-12)
            if use_annual:
                z = np.full(5, np.nan)
                z[good] = np.tanh((raw[good] - raw[good].mean()) / p["annual_scale"])
                timing[name] = smooth_partial(z)
            usage.append(dict(factor_name=name, family=family, used_for_period_mean=bool(use_total), used_for_annual_timing=bool(use_annual),
                historical_finite_cells=int(good.sum()), static_context=p["static"], source_missing_filled=False,
                global_factor_eligible=p["cumulative_enabled"] or p["annual_enabled"], quality_weight=p["quality"]))
        weights = {name:parameters[name]["quality"] for name in names}
        cumulative[family] = pool_family(totals, family, 1, weights)
        annual[family] = pool_family(timing, family, 5, weights)
    axis = lambda names, table, length: mean_available([table[n] for n in names], [FAMILY_WEIGHT[n] for n in names], length)
    d = axis(TOTAL_AXES["demand"], cumulative, 1)[0]
    p = axis(TOTAL_AXES["production"], cumulative, 1)[0]
    b = axis(TOTAL_AXES["background"], cumulative, 1)[0]
    if extra_background:
        b = mean_available([np.array([b]), mean_available(extra_background)])[0]
    interaction = b * mean_available([np.array([d]), np.array([p])])[0]
    activity = axis(TIMING_AXES["activity"], annual, 5)
    demand = axis(TIMING_AXES["demand_shock"], annual, 5)
    # A masked model operator is not a filled source measurement.
    activity = np.where(np.isfinite(activity), activity, 0.); activity -= activity.mean()
    demand = np.where(np.isfinite(demand), demand, 0.); demand -= demand.mean()
    design = np.column_stack([np.ones(5), np.full(5, d), np.full(5, p), np.full(5, interaction), activity, demand])
    missing = ~np.isfinite(design)
    design[missing] = 0.
    return design, usage, dict(feature_envelope_extrapolation=outside, missing_mean_coordinates=int(missing[0].sum()),
        available_period_families=sum(np.isfinite(v).any() for v in cumulative.values()), available_timing_families=sum(np.isfinite(v).any() for v in annual.values()))


def composition_scenarios(panel, excluded_donors=()):
    a = panel[panel.year.eq(2020)].copy().set_index("country_id")
    q = pd.to_numeric(a.q1_nonres_source_volume_share_2020, errors="raise")
    qualified = a.composition_source_qualified_2020.map(flag) & q.between(0, 1)
    donors = a.loc[qualified & ~a.index.isin(excluded_donors)].copy()
    donors["q"] = q.loc[donors.index]
    result = {}
    for c, row in a.iterrows():
        if qualified.loc[c]:
            result[c] = dict(q=float(q.loc[c]), role="native_volume_share_equal_conversion_scenario", donor_count=0, source_q=float(q.loc[c]))
            continue
        anchor = float(row.fixed_2020_total_anchor_m2)
        if not np.isfinite(anchor) or anchor <= 0:
            result[c] = dict(q=None, role="missing_level_and_composition", donor_count=0, source_q=None)
            continue
        chosen, role = None, None
        candidates = [
            (donors[donors.m49_region.eq(row.m49_region) & donors.income_tier_as_recorded.eq(row.income_tier_as_recorded)], "region_income_volume_share_median_scenario"),
            (donors[donors.m49_region.eq(row.m49_region)], "region_volume_share_median_scenario"),
            (donors, "global_volume_share_median_scenario")]
        for group, name in candidates:
            if len(group) >= 5:
                chosen, role = group, name
                break
        if chosen is None:
            result[c] = dict(q=None, role="insufficient_composition_donors", donor_count=0, source_q=None)
        else:
            result[c] = dict(q=float(chosen.q.median()), role=role, donor_count=len(chosen), source_q=None)
    return result


def cumulative_operator(annual):
    out = np.zeros((16,) + annual.shape[1:])
    for j, y in enumerate(YEARS):
        if y < 2020:
            out[j] = -annual[(RATE_YEARS > y) & (RATE_YEARS <= 2020)].sum(axis=0)
        elif y > 2020:
            out[j] = annual[(RATE_YEARS > 2020) & (RATE_YEARS <= y)].sum(axis=0)
    return out


def encode_panel(panel, model, *, damping=FUTURE_DAMPING, excluded_donors=()):
    view = historical_source_view(panel)
    qmeta = composition_scenarios(panel, excluded_donors)
    train_geometry = np.array(model.get("geometry_inverse", np.eye(6)), float)
    result, usage, coordinates, diagnostics = {}, [], [], []
    for c, g in view.groupby("country_id", sort=True):
        x, used, diag = encode_country(g, model["feature_parameters"])
        leverage = float(np.trace(x @ train_geometry @ x.T) / 5)
        maximum = model.get("training_max_leverage", float("inf"))
        transfer = min(1., maximum / leverage) if leverage > 0 else 1.
        x *= transfer
        full = panel[panel.country_id.eq(c)].sort_values("year")
        historical = g.annual_log_surface_change_proxy.to_numpy(float)
        good = np.isfinite(historical)
        h0 = float(historical[good].mean()) if good.sum() >= 3 else np.nan
        hrole = "legacy_GHSL_endpoint_mean"
        if not np.isfinite(h0):
            points = full.set_index("year").wup_built_surface_km2
            if points.get(2015, np.nan) > 0 and points.get(2020, np.nan) > 0:
                h0 = float(np.log(points[2020] / points[2015]) / 5)
                hrole = "within_WUP_historical_surface_fallback"
            else:
                h0 = model["fallback_horizontal_log_rate"]
                hrole = "shared_training_horizontal_median_fallback"
        future_ok = bool(full.wup_full2025_2030_positive_ratio_support.map(flag).all())
        h = np.full(15, h0)
        for j, y in enumerate(RATE_YEARS):
            if y > 2020 and future_ok:
                z = full.loc[full.year.eq(y), "wup_annual_log_surface_change"].iloc[0]
                if np.isfinite(z):
                    h[j] = float(z)
                else:
                    future_ok = False
        if not future_ok:
            h[5:] = h0
        future_seed = np.r_[x[0, :4], x[-3:, 4:].mean(axis=0)]
        design = np.vstack([x, np.array([future_seed * damping ** (y - 2020) for y in range(2021, 2031)])])
        zr = np.column_stack([design, np.zeros(15)]) * RATE_SCALE
        zn = zr.copy()
        zn[:, 6] = RATE_SCALE * np.r_[np.ones(5), np.array([damping ** (y - 2020) for y in range(2021, 2031)])] if model["contrast_enabled"] else 0.
        q = qmeta[c]["q"]
        result[c] = dict(base=cumulative_operator(h), br=cumulative_operator(zr), bn=cumulative_operator(zn),
            h=h, zr=zr, zn=zn, q=q, anchor=float(full.fixed_2020_total_anchor_m2.iloc[0]))
        for u in used:
            usage.append(dict(country_id=c, **u))
        for j, year in enumerate(RATE_YEARS):
            coordinates.append(dict(country_id=c, interval_end_year=int(year), horizontal_annual_log_prior=h[j], horizontal_source=hrole if year <= 2020 else "WUP_surface_projection_related_interpolation" if future_ok else "shared_historical_horizontal_fallback",
                correction_scenario="historical_qualified_coordinates" if year <= 2020 else "damped_historical_coordinate_continuation_not_observed_drivers",
                future_damping=1. if year <= 2020 else damping ** (year - 2020),
                **{name:float(value) for name, value in zip(COEFFICIENTS[:6], design[j])}))
        diagnostics.append(dict(country_id=c, **diag, q1_nonres_source_volume_share_2020=qmeta[c]["source_q"],
            assumed_nonres_GFA_share_2020=q, composition_scenario_role=qmeta[c]["role"], composition_donor_count=qmeta[c]["donor_count"],
            correction_transfer_weight=transfer, design_leverage=leverage, historical_horizontal_role=hrole,
            WUP_future_used=future_ok, missing_positive_level=not np.isfinite(result[c]["anchor"]) or result[c]["anchor"] <= 0,
            composition_validated=False, applicability_rule_validated=False))
    return result, pd.DataFrame(usage), pd.DataFrame(coordinates), pd.DataFrame(diagnostics)


def observation_logratio(state, beta, sector, year):
    j = int(year) - 2015
    rr, nn = float(state["br"][j] @ beta), float(state["bn"][j] @ beta)
    if sector == "residential":
        return state["base"][j] + rr, state["br"][j]
    if sector == "non_residential":
        return state["base"][j] + nn, state["bn"][j]
    if sector != "total":
        raise ValueError("Unsupported observation sector")
    q = state["q"]
    if q is None:
        raise ValueError("Total observation requires declared composition scenario")
    if q == 0:
        return state["base"][j] + rr, state["br"][j]
    if q == 1:
        return state["base"][j] + nn, state["bn"][j]
    log_r, log_n = np.log1p(-q) + rr, np.log(q) + nn
    total = np.logaddexp(log_r, log_n)
    nr = np.exp(log_n - total)
    return state["base"][j] + total, (1 - nr) * state["br"][j] + nr * state["bn"][j]


def training_blocks(observations, states):
    blocks, weights = [], []
    selected = observations[observations.relative_change_training_eligible.map(flag) & ~observations.normalization_identity.map(flag)].copy()
    for c, cg in selected.groupby("country_id", sort=True):
        sources = list(cg.groupby("source_family_id", sort=True))
        members, precision = [], []
        for source, sg in sources:
            channels = list(sg.groupby("observation_channel", sort=True))
            for channel, gg in channels:
                gg = gg.sort_values("year")
                if gg.year.duplicated().any():
                    raise ValueError("Duplicated source/channel/date observation")
                m = len(gg)
                p = np.eye(m) - np.ones((m,m)) / (m + 1.)
                p /= np.trace(p) * len(sources) * len(channels)
                precision.append(p)
                members.extend(gg.to_dict("records"))
                weights.append(dict(country_id=c, source_family_id=source, observation_channel=channel,
                    nonanchor_observations=m, source_count=len(sources), channel_count=len(channels),
                    precision_trace=float(np.trace(p)), country_information_budget=1., working_logratio_scale=OBSERVATION_SCALE))
        size = sum(len(p) for p in precision); full = np.zeros((size,size)); start = 0
        for p in precision:
            full[start:start+len(p),start:start+len(p)] = p; start += len(p)
        if not np.isclose(np.trace(full), 1.):
            raise ValueError("Country information budget not one")
        blocks.append((c, members, full))
    return blocks, pd.DataFrame(weights)


def objective(beta, states, blocks, derivatives=False):
    value = .5 * float((RIDGE * beta) @ beta)
    gradient, normal = RIDGE * beta, np.diag(RIDGE)
    for c, members, p in blocks:
        predicted = [observation_logratio(states[c], beta, r["sector"], r["year"]) for r in members]
        residual = (np.array([v for v, _ in predicted]) - np.array([r["native_log_ratio_to_2020"] for r in members])) / OBSERVATION_SCALE
        jac = np.stack([j for _, j in predicted]) / OBSERVATION_SCALE
        norm = float(np.sqrt(max(0., residual @ p @ residual)))
        robust = min(1., 1.35 / norm) if norm else 1.
        value += .5 * norm ** 2 if norm <= 1.35 else 1.35 * (norm - .675)
        gradient += robust * jac.T @ p @ residual
        normal += robust * jac.T @ p @ jac
    return (value, gradient, normal) if derivatives else value


def fit_model(panel, observations, qualities, *, excluded_countries=(), removed_groups=(), max_year=None):
    if max_year is not None and max_year < 2020:
        raise ValueError("2020-normalized protocol cannot fit a pre-2020 forecast origin")
    obs = observations[~observations.country_id.isin(excluded_countries)].copy()
    if max_year is not None:
        obs = obs[obs.year.le(max_year)].copy()
    if obs.country_id.isin(RESERVED).any() or not obs.observation_role.eq("exposed_native_change_development_only").all():
        raise ValueError("Reserved/non-development reference cannot enter fit")
    obs = obs[obs.relative_change_training_eligible.map(flag)].copy()
    countries = sorted(obs.loc[~obs.normalization_identity.map(flag), "country_id"].unique())
    if len(countries) < 3:
        raise ValueError("At least three development countries required")
    view = historical_source_view(panel)
    parameters = feature_parameters(view, countries, qualities, removed_groups)
    paired = obs.groupby("country_id").sector.apply(lambda s: {"total", "residential"} <= set(s)).sum()
    horizontal = view[view.country_id.isin(countries)].groupby("country_id").annual_log_surface_change_proxy.mean().dropna()
    model = dict(version="v16", method="shared_two_state_net_stock_change", coefficients_count=7,
        coefficient_names=COEFFICIENTS, training_countries=countries, training_observations=int((~obs.normalization_identity.map(flag)).sum()),
        contrast_enabled=bool(paired >= 2), paired_Total_RES_countries=int(paired), feature_parameters=parameters,
        fallback_horizontal_log_rate=float(horizontal.median()), removed_groups=list(removed_groups),
        rate_scale=RATE_SCALE, working_logratio_scale=OBSERVATION_SCALE, future_damping=FUTURE_DAMPING,
        ridge=RIDGE.tolist(), maximum_training_year=int(obs.year.max()), excluded_countries=list(excluded_countries),
        official_area_required_at_inference=False, flows_separately_identified=False, calibrated_confidence_intervals=False)
    temp, _, _, _ = encode_panel(panel, model, excluded_donors=excluded_countries)
    xx = np.vstack([temp[c]["zr"][:5,:6] / RATE_SCALE for c in countries])
    inverse = np.linalg.inv(xx.T @ xx / 5 + np.eye(6))
    model["geometry_inverse"] = inverse.tolist()
    model["training_max_leverage"] = max(float(np.trace((temp[c]["zr"][:5,:6] / RATE_SCALE) @ inverse @ (temp[c]["zr"][:5,:6] / RATE_SCALE).T) / 5) for c in countries)
    states, usage, coordinates, diagnostics = encode_panel(panel, model, excluded_donors=excluded_countries)
    blocks, budget = training_blocks(obs, states)
    beta = np.zeros(7); converged = False
    for iteration in range(400):
        value, grad, normal = objective(beta, states, blocks, True)
        if np.max(np.abs(grad)) < 1e-9:
            converged = True; break
        step = np.linalg.solve(normal, -grad)
        scale = 1.
        while scale > 2 ** -30 and objective(beta + scale * step, states, blocks) > value + 1e-4 * scale * (grad @ step):
            scale /= 2
        updated = beta + scale * step
        if np.max(np.abs(updated - beta)) < 1e-12:
            beta = updated; break
        beta = updated
    final, grad, _ = objective(beta, states, blocks, True)
    if np.max(np.abs(grad)) < 1e-7:
        converged = True
    if not converged:
        raise RuntimeError("Shared model optimizer did not reach stationary point")
    model.update(coefficients=beta.tolist(), optimizer_iterations=iteration + 1, objective=float(final),
        gradient_inf_norm=float(np.max(np.abs(grad))), converged=converged,
        preprocessing_scope="Training-country labels and predictor transformations only; composition donor pool uses qualified unlabeled source contexts excluding held-out donor", 
        covariance="I+11T within each native2020ratio channel; inverse trace normalized and source/channel budgeted; whole-country robust block")
    return model, usage, coordinates, diagnostics, budget


def predict_model(panel, model, *, damping=FUTURE_DAMPING):
    states, usage, coordinates, diagnostics = encode_panel(panel, model, damping=damping, excluded_donors=model.get("excluded_countries", []))
    beta = np.array(model["coefficients"]); rows = []
    for c, state in states.items():
        a, q = state["anchor"], state["q"]
        level_available = np.isfinite(a) and a > 0
        complete = level_available and q is not None
        cr, cn = state["base"] + state["br"] @ beta, state["base"] + state["bn"] @ beta
        safe = np.isfinite(cr).all() and np.isfinite(cn).all() and max(np.max(abs(cr)), np.max(abs(cn))) < 50
        complete = complete and safe
        if complete:
            r0 = a * (1 - q); n0 = a - r0
            r, n = r0 * np.exp(cr), n0 * np.exp(cn)
            total = r + n
            total[5] = a
        else:
            r, n, total = np.full(16, np.nan), np.full(16, np.nan), np.full(16, np.nan)
            if level_available:
                total[5] = a
        for j, y in enumerate(YEARS):
            rows.append(dict(country_id=c, year=int(y), residential_gfa_m2=r[j], non_residential_gfa_m2=n[j], total_gfa_m2=total[j],
                fixed_2020_total_anchor_m2=a, actual_GFA_truth=False,
                residential_ratio_to_2020=float(np.exp(cr[j])) if complete and q < 1 else np.nan,
                non_residential_ratio_to_2020=float(np.exp(cn[j])) if complete and q > 0 else np.nan,
                total_ratio_to_2020=total[j] / a if level_available else np.nan,
                residential_annual_net_change_m2=r[j] - r[j-1] if j else np.nan,
                non_residential_annual_net_change_m2=n[j] - n[j-1] if j else np.nan,
                total_annual_net_change_m2=total[j] - total[j-1] if j else np.nan,
                total_annual_growth_percent=100 * (total[j] / total[j-1] - 1) if j and total[j-1] > 0 else np.nan,
                accounting_residual_m2=r[j] + n[j] - total[j],
                estimate_role="missing_qualified_level" if not level_available else "fixed2020_physical_proxy_anchor" if y == 2020 else "unsupported_extreme_model_path" if not safe else "missing_composition" if not complete else "historical_backcast_research_estimate" if y < 2020 else "retrospective_research_estimate" if y <= 2025 else "2026_nowcast_projection" if y == 2026 else "conditional_future_projection",
                independently_observed_GFA=False, complete_GFA_definition_bridge=False,
                uncertainty_status="Uncalibrated anchor, native-definition, composition and dynamic-model uncertainty; scenarios are not CI",
                new_construction_and_demolition_identified=False, default_changed=False, model_version="v16"))
    output = pd.DataFrame(rows).merge(diagnostics, on="country_id", validate="many_to_one")
    output["annual_growth_over10percent_flag"] = output.total_annual_growth_percent.abs().gt(10)
    return output, usage, coordinates, diagnostics
