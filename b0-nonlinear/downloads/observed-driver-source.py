"""One prespecified observed-driver continuation of the frozen v16 architecture.

Only two annual departure coordinates change after 2020. Latest-vintage national
statistics are predictors, not independent GFA labels or operational hindcasts.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from v7 import shared_dynamic_stock as base

FACTORS = (
    "annual_log_population_change", "annual_log_urban_population_change",
    "annual_log_real_gdp_per_capita_change", "annual_log_real_gfcf_change",
)
PREFIX = "observed__"
VERSION = "v16_observed_driver_extension"
candidate_observed_source_columns = tuple(
    PREFIX + n + suffix for n in FACTORS
    for suffix in ("", "__qualified", "__source_role", "__available_by", "__source_vintage")
)


def cutoff_panel(panel, cutoff):
    """Mask future source values AND status; latest release is not a vintage archive."""
    out = panel.copy(deep=True)
    future = out.year.gt(cutoff)
    for col in out:
        if col.startswith(PREFIX) or col.startswith("wup_"):
            if pd.api.types.is_bool_dtype(out[col]) or col.endswith("__qualified"):
                out.loc[future, col] = False
            else:
                out.loc[future, col] = np.nan
    if "wup_full2025_2030_positive_ratio_support" in out:
        out["wup_full2025_2030_positive_ratio_support"] = False
    return out


def _qualified_values(full, name):
    key = PREFIX + name
    if key not in full or key + "__qualified" not in full:
        return pd.Series(np.nan, index=full.year.to_numpy())
    values = pd.to_numeric(full[key], errors="coerce").where(full[key + "__qualified"].map(base.flag))
    result = pd.Series(values.to_numpy(float), index=full.year.to_numpy())
    if name in base.PIPELINE:
        previous = result.reindex(result.index - 1).to_numpy()
        now = result.to_numpy()
        result[:] = np.where(np.isfinite(now) & np.isfinite(previous), (now + previous) / 2, np.nan)
    return result


def encode_panel(panel, model):
    states, usage, coordinates, diagnostics = base.encode_panel(
        panel, model, excluded_donors=model.get("excluded_countries", []))
    historical = base.historical_source_view(panel)
    extra_usage = []
    for country, state in states.items():
        full = panel.loc[panel.country_id.eq(country)].sort_values("year")
        hist = historical.loc[historical.country_id.eq(country)]
        signals = {}
        for name in FACTORS:
            parameter = model["feature_parameters"][name]
            own = base.transformed(hist[name].to_numpy(float), name)
            good = np.isfinite(own)
            if not parameter["annual_enabled"] or good.sum() < 3:
                continue
            observed = _qualified_values(full, name)
            raw = base.transformed(observed.to_numpy(float), name)
            z = np.tanh((raw - own[good].mean()) / parameter["annual_scale"])
            # A causal smoother has no future-looking annual source dependency.
            prior = pd.Series(z, index=observed.index).reindex(observed.index - 1).to_numpy()
            smooth = np.where(np.isfinite(z) & np.isfinite(prior), (2*z + prior)/3, z)
            signals[name] = pd.Series(smooth, index=observed.index)
        coordinate_rows = coordinates.country_id.eq(country)
        transfer = float(diagnostics.loc[diagnostics.country_id.eq(country), "correction_transfer_weight"].iloc[0])
        axis_seen = {4: None, 5: None}
        axis_counts = {4: 0, 5: 0}
        # State arrays are copied: the original frozen operator is never mutated.
        zr, zn = state["zr"].copy(), state["zn"].copy()
        for j, year in enumerate(base.RATE_YEARS):
            if year <= 2020:
                continue
            roles = {}
            for axis_index, axis in [(4, "activity"), (5, "demand_shock")]:
                family_values, family_weights = [], []
                used = []
                for family in base.TIMING_AXES[axis]:
                    values, weights = [], []
                    for name, signal in signals.items():
                        p = model["feature_parameters"][name]
                        value = signal.get(int(year), np.nan)
                        if p["family"] == family and np.isfinite(value):
                            values.append(float(value)); weights.append(p["quality"]); used.append(name)
                    if values:
                        family_values.append(float(np.average(values, weights=weights)))
                        family_weights.append(base.FAMILY_WEIGHT[family])
                if family_values:
                    value = transfer * float(np.average(family_values, weights=family_weights))
                    axis_seen[axis_index] = (int(year), value)
                    axis_counts[axis_index] += 1
                    role = "qualified_latest_vintage_reported_or_estimated_driver"
                elif axis_seen[axis_index] is not None:
                    last_year, last = axis_seen[axis_index]
                    value = last * base.FUTURE_DAMPING ** (int(year) - last_year)
                    role = "shared_damped_continuation_of_last_observed_axis_not_observed_source"
                else:
                    value = float(state["zr"][j, axis_index] / base.RATE_SCALE)
                    role = "unchanged_v16_damped_historical_axis_no_qualified_new_source"
                if role != "unchanged_v16_damped_historical_axis_no_qualified_new_source":
                    zr[j, axis_index] = zn[j, axis_index] = value * base.RATE_SCALE
                where = coordinate_rows & coordinates.interval_end_year.eq(year)
                coordinates.loc[where, base.COEFFICIENTS[axis_index]] = value
                coordinates.loc[where, axis + "_extension_role"] = role
                coordinates.loc[where, axis + "_observed_factors"] = ";".join(used)
                roles[axis] = role
                extra_usage.append(dict(country_id=country, interval_end_year=int(year), axis=axis,
                    factor_names=";".join(used), observed_factor_count=len(used), extension_role=role,
                    raw_missing_filled=False, operational_forecast_vintage_qualified=False))
            where = coordinate_rows & coordinates.interval_end_year.eq(year)
            coordinates.loc[where, "correction_scenario"] = "prespecified_observed_driver_annual_departure_extension"
        state["zr"], state["zn"] = zr, zn
        state["br"], state["bn"] = base.cumulative_operator(zr), base.cumulative_operator(zn)
        row = diagnostics.country_id.eq(country)
        diagnostics.loc[row, "observed_activity_axis_years_2021_2030"] = axis_counts[4]
        diagnostics.loc[row, "observed_demand_axis_years_2021_2030"] = axis_counts[5]
        diagnostics.loc[row, "new_annual_axis_weights_fitted"] = False
    return states, usage, coordinates, diagnostics, pd.DataFrame(extra_usage)


def fit_model(panel, observations, qualities, *, excluded_countries=(), removed_groups=(), max_year=None):
    """Refit the same seven parameters; transformations use training countries only."""
    if max_year is not None and max_year < 2020:
        raise ValueError("2020-normalized model cannot pretend a pre-2020 forecast origin")
    obs = observations.loc[~observations.country_id.isin(excluded_countries)].copy()
    if max_year is not None:
        obs = obs.loc[obs.year.le(max_year)].copy()
    if obs.country_id.isin(base.RESERVED).any() or not obs.observation_role.eq("exposed_native_change_development_only").all():
        raise ValueError("Reserved/non-development labels cannot enter candidate fit")
    obs = obs.loc[obs.relative_change_training_eligible.map(base.flag)].copy()
    countries = sorted(obs.loc[~obs.normalization_identity.map(base.flag), "country_id"].unique())
    if len(countries) < 3:
        raise ValueError("At least three development countries required")
    view = base.historical_source_view(panel)
    parameters = base.feature_parameters(view, countries, qualities, removed_groups)
    paired = obs.groupby("country_id").sector.apply(lambda s: {"total", "residential"} <= set(s)).sum()
    horizontal = view.loc[view.country_id.isin(countries)].groupby("country_id").annual_log_surface_change_proxy.mean().dropna()
    if horizontal.empty or not np.isfinite(horizontal).all():
        raise ValueError("No qualified training horizontal fallback")
    model = dict(version=VERSION, method="shared_two_state_stock_observed_annual_departure", coefficients_count=7,
        coefficient_names=base.COEFFICIENTS, training_countries=countries,
        training_observations=int((~obs.normalization_identity.map(base.flag)).sum()),
        contrast_enabled=bool(paired >= 2), paired_Total_RES_countries=int(paired), feature_parameters=parameters,
        fallback_horizontal_log_rate=float(horizontal.median()), removed_groups=list(removed_groups),
        rate_scale=base.RATE_SCALE, working_logratio_scale=base.OBSERVATION_SCALE,
        future_damping=base.FUTURE_DAMPING, ridge=base.RIDGE.tolist(), maximum_training_year=int(obs.year.max()),
        excluded_countries=list(excluded_countries), official_area_required_at_inference=False,
        flows_separately_identified=False, calibrated_confidence_intervals=False,
        observed_factors=list(FACTORS), latest_vintage_predictors=True, operational_forecast_vintage_validated=False)
    model["observed_driver_preprocessing"] = dict(
        training_countries=countries,
        scale_source="unchanged v16 feature_parameters fitted only on eligible training-country 2016–2020 predictors",
        target_country_center="own unlabeled historical qualified predictor mean, never held-out area labels",
        future_sources_used_for_preprocessing=False,
        source_quality_weights_fitted=False)
    temp, *_ = base.encode_panel(panel, model, excluded_donors=excluded_countries)
    xx = np.vstack([temp[c]["zr"][:5, :6] / base.RATE_SCALE for c in countries])
    inverse = np.linalg.inv(xx.T @ xx / 5 + np.eye(6))
    model["geometry_inverse"] = inverse.tolist()
    model["training_max_leverage"] = max(float(np.trace(
        (temp[c]["zr"][:5, :6] / base.RATE_SCALE) @ inverse @
        (temp[c]["zr"][:5, :6] / base.RATE_SCALE).T) / 5) for c in countries)
    states, usage, coordinates, diagnostics, _ = encode_panel(panel, model)
    blocks, budget = base.training_blocks(obs, states)
    beta = np.zeros(7)
    for iteration in range(400):
        value, gradient, normal = base.objective(beta, states, blocks, True)
        if np.max(np.abs(gradient)) < 1e-9:
            break
        step = np.linalg.solve(normal, -gradient)
        scale = 1.
        while scale > 2 ** -30 and base.objective(beta + scale * step, states, blocks) > value + 1e-4 * scale * (gradient @ step):
            scale /= 2
        updated = beta + scale * step
        if np.max(np.abs(updated - beta)) < 1e-12:
            beta = updated
            break
        beta = updated
    value, gradient, _ = base.objective(beta, states, blocks, True)
    if not np.isfinite(beta).all() or np.max(np.abs(gradient)) >= 1e-7:
        raise RuntimeError("Shared candidate optimizer not stationary")
    model.update(coefficients=beta.tolist(), optimizer_iterations=iteration+1, objective=float(value),
        gradient_inf_norm=float(np.max(np.abs(gradient))), converged=True,
        preprocessing_scope="Training-country historical2016–2020 transformations only; qualified unlabeled composition donors excluding held country")
    return model, usage, coordinates, diagnostics, budget


def predict_model(panel, model):
    states, usage, coordinates, diagnostics, extension = encode_panel(panel, model)
    beta = np.asarray(model["coefficients"], float)
    rows = []
    for country, state in states.items():
        anchor, q = state["anchor"], state["q"]
        level = np.isfinite(anchor) and anchor > 0
        cr, cn = state["base"] + state["br"] @ beta, state["base"] + state["bn"] @ beta
        safe = np.isfinite(cr).all() and np.isfinite(cn).all() and max(np.max(abs(cr)), np.max(abs(cn))) < 50
        complete = level and q is not None and safe
        if complete:
            r0 = anchor*(1-q); n0 = anchor-r0
            residential, nonres = r0*np.exp(cr), n0*np.exp(cn)
            total = residential+nonres; total[5] = anchor
        else:
            residential, nonres, total = (np.full(16, np.nan) for _ in range(3))
            if level:
                total[5] = anchor
        for j, year in enumerate(base.YEARS):
            rows.append(dict(country_id=country, year=int(year), residential_gfa_m2=residential[j],
                non_residential_gfa_m2=nonres[j], total_gfa_m2=total[j], fixed_2020_total_anchor_m2=anchor,
                residential_ratio_to_2020=float(np.exp(cr[j])) if complete and q < 1 else np.nan,
                non_residential_ratio_to_2020=float(np.exp(cn[j])) if complete and q > 0 else np.nan,
                total_ratio_to_2020=total[j]/anchor if level else np.nan,
                residential_annual_net_change_m2=residential[j]-residential[j-1] if j else np.nan,
                non_residential_annual_net_change_m2=nonres[j]-nonres[j-1] if j else np.nan,
                total_annual_net_change_m2=total[j]-total[j-1] if j else np.nan,
                total_annual_growth_percent=100*(total[j]/total[j-1]-1) if j and total[j-1]>0 else np.nan,
                accounting_residual_m2=residential[j]+nonres[j]-total[j], actual_GFA_truth=False,
                independently_observed_GFA=False, complete_GFA_definition_bridge=False,
                uncertainty_status="Uncalibrated anchor, definition, composition, driver and model uncertainty; not CI",
                new_construction_and_demolition_identified=False, default_changed=False, model_version=VERSION,
                estimate_role="missing_qualified_level" if not level else "fixed2020_physical_proxy_anchor" if year==2020
                    else "unsupported_path" if not complete else "historical_backcast_research_estimate" if year<2020
                    else "latest_vintage_driver_conditioned_research_estimate" if year<=2025 else "conditional_future_projection"))
    output = pd.DataFrame(rows).merge(diagnostics, on="country_id", validate="many_to_one")
    output["annual_growth_over10percent_flag"] = output.total_annual_growth_percent.abs().gt(10)
    return output, usage, coordinates, diagnostics
