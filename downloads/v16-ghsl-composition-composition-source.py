"""One deterministic, 2020-preserving GHSL composition extension of v16.

Only the residential/non-residential allocation changes. Native volume changes
do not identify floor-function GFA, and projected epochs are not observations.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

VERSION = 'v16_dynamic_GHSL_composition_candidate'
YEARS = tuple(range(2015, 2031))
EPOCHS = (2015, 2020, 2025, 2030)


def flag(value):
    return value is True or isinstance(value, (bool, np.bool_)) and bool(value) or str(value).lower() == 'true'


def interpolate_volume(endpoints, years):
    """Preserve exact source endpoints; never manufacture a positive zero."""
    years = np.asarray(years, int)
    keys = sorted(endpoints)
    values = np.asarray([endpoints[k] for k in keys], float)
    if len(keys) < 2 or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError('Finite nonnegative volume endpoints required')
    if min(years) < min(keys) or max(years) > max(keys) or any(b-a != 5 for a,b in zip(keys,keys[1:])):
        raise ValueError('No extrapolation or interpolation across a missing native epoch')
    result, roles = [], []
    for year in years:
        if year in endpoints:
            result.append(float(endpoints[year])); roles.append('native_modeled_epoch')
            continue
        left=max(k for k in keys if k<year);right=min(k for k in keys if k>year)
        a,b=float(endpoints[left]),float(endpoints[right]);w=(int(year)-left)/(right-left)
        if min(a,b)>0:
            value=np.exp((1-w)*np.log(a)+w*np.log(b));role='log_volume_interpolation'
        else:
            value=(1-w)*a+w*b;role='linear_volume_interpolation_structural_zero_endpoint'
        result.append(float(value));roles.append(role)
    return np.asarray(result),roles


def qualified_bundle(frame, country, epochs):
    selected=frame.loc[frame.country_id.eq(country)&frame.year.isin(epochs)].copy()
    if selected.duplicated(['country_id','year']).any():
        raise ValueError('Duplicate country/epoch source')
    if set(selected.year)!=set(epochs) or not selected.qualified.map(flag).all():
        return None
    for name in ['geometry_sha256','request_sha256']:
        if name not in selected or selected[name].isna().any() or selected[name].nunique()!=1:
            raise ValueError('Qualified epoch bundle has inconsistent source/geometry identity')
    by=selected.set_index('year').sort_index()
    a=by[['total_volume_m3','nres_volume_m3']].to_numpy(float)
    if not np.isfinite(a).all() or (a[:,0]<=0).any() or (a[:,1]<0).any() or (a[:,1]>a[:,0]).any():
        raise ValueError('An allegedly qualified source has invalid sector volumes')
    return by


def build_source_paths(historical, native, countries):
    """Reuse qualified 100m history; use a separate qualified future triplet.

Each period is normalized to its own source2020, so a different source-grid
baseline does not silently revise the inherited2020 allocation.
"""
    rows=[]
    for country in countries:
        for epochs,years,period in [((2015,2020),range(2015,2021),'historical'),
                                    ((2020,2025,2030),range(2021,2031),'projected')]:
            bundle=None;resolution=None;origin=None
            if period=='historical':
                bundle=qualified_bundle(historical,country,epochs)
                if bundle is not None:resolution=100;origin='frozen_qualified_native100m_history'
            if bundle is None:
                bundle=qualified_bundle(native,country,epochs)
                if bundle is not None:resolution=1000;origin='new_common_grid_native1000m_volume'
            if bundle is None:
                for year in years:
                    rows.append(dict(country_id=country,year=year,transfer_qualified=False,
                        source_path_role='unqualified_epoch_bundle_preserve_v16_composition',
                        source_period=period,source_resolution_m=np.nan,
                        source_nonres_share=np.nan,nonres_volume_index_2020=np.nan,
                        res_volume_index_2020=np.nan,temporal_role='missing_source_not_zero'))
                continue
            n_end=bundle.nres_volume_m3.to_dict()
            r_end=(bundle.total_volume_m3-bundle.nres_volume_m3).to_dict()
            interpolation_years=sorted(set(years)|{2020})
            n,nt=interpolate_volume(n_end,interpolation_years)
            r,rt=interpolate_volume(r_end,interpolation_years)
            supported=n_end[2020]>0 and r_end[2020]>0
            for j,year in enumerate(interpolation_years):
                if year not in years:continue
                total=n[j]+r[j]
                temporal=('historical_modeled_native_epoch_fixed2018_height' if year in (2015,2020)
                    else 'historical_modeled_annual_interpolation' if year<2020
                    else 'projected_native_GHSL_epoch_not_observed' if year in (2025,2030)
                    else 'conditional_interpolation_involving_GHSL_projected_epochs')
                rows.append(dict(country_id=country,year=year,transfer_qualified=bool(supported),
                    source_path_role=origin if supported else 'zero_2020_component_prevents_relative_transfer',
                    source_period=period,source_resolution_m=resolution,source_nonres_share=n[j]/total,
                    source_total_volume_m3=total,source_nonres_volume_m3=n[j],source_res_complement_volume_m3=r[j],
                    source_2020_nonres_share=n_end[2020]/(n_end[2020]+r_end[2020]),
                    nonres_volume_index_2020=n[j]/n_end[2020] if n_end[2020]>0 else np.nan,
                    res_volume_index_2020=r[j]/r_end[2020] if r_end[2020]>0 else np.nan,
                    temporal_role=temporal,nonres_interpolation_rule=nt[j],res_interpolation_rule=rt[j],
                    source_geometry_sha256=str(bundle.geometry_sha256.iloc[0]),
                    source_request_sha256=str(bundle.request_sha256.iloc[0]),
                    source_dataset='GHS-BUILT-V R2023A',volume_share_is_verified_GFA_share=False,
                    historical_use_change_observed=False))
    result=pd.DataFrame(rows).sort_values(['country_id','year']).reset_index(drop=True)
    if result.duplicated(['country_id','year']).any():raise ValueError('Duplicate annual source row')
    return result


def apply_composition(baseline, source_paths):
    """Transfer relative composition changes, keeping every Total and2020 triplet."""
    required={'country_id','year','total_gfa_m2','residential_gfa_m2','non_residential_gfa_m2'}
    if not required.issubset(baseline):raise ValueError('Missing baseline state fields')
    if baseline.duplicated(['country_id','year']).any() or source_paths.duplicated(['country_id','year']).any():
        raise ValueError('Ambiguous country/year identities')
    original=baseline.copy(deep=True)
    state=baseline[['total_gfa_m2','residential_gfa_m2','non_residential_gfa_m2']].to_numpy(float)
    present=np.isfinite(state[:,0])
    if (not np.isfinite(state[present]).all() or (state[present]<0).any()
            or not np.allclose(state[present,1]+state[present,2],state[present,0],rtol=1e-14,atol=1e-6)):
        raise ValueError('Invalid or nonconserving baseline state')
    result=baseline.copy(deep=True)
    lookup=source_paths.set_index(['country_id','year'])
    for col in ['residential_gfa_m2','non_residential_gfa_m2']:
        result['retained_v16_'+col]=result[col]
    result['retained_v16_nonres_share']=result.non_residential_gfa_m2/result.total_gfa_m2
    for country,g in result.groupby('country_id',sort=False):
        anchor=g.loc[g.year.eq(2020)]
        if len(anchor)!=1:raise ValueError('Exactly one2020 reference per country required')
        t0,r0,n0=anchor[['total_gfa_m2','residential_gfa_m2','non_residential_gfa_m2']].iloc[0].to_numpy(float)
        qualified_anchor=np.isfinite([t0,r0,n0]).all() and t0>0 and min(r0,n0)>=0
        if qualified_anchor and not np.isclose(r0+n0,t0,rtol=1e-14,atol=1e-6):raise ValueError('Baseline components do not conserve')
        q0=n0/t0 if qualified_anchor else np.nan
        for index,row in g.iterrows():
            key=(country,int(row.year));source=lookup.loc[key] if key in lookup.index else None
            role='retained_v16_composition_missing_qualified_source'
            used=False
            if row.year==2020:
                role='inherited_2020_components_preserved_exactly'
            elif qualified_anchor and np.isfinite(row.total_gfa_m2) and row.total_gfa_m2>0 and source is not None and flag(source.transfer_qualified):
                mn=float(source.nonres_volume_index_2020);mr=float(source.res_volume_index_2020)
                denominator=q0*mn+(1-q0)*mr
                if not np.isfinite([mn,mr,denominator]).all() or min(mn,mr)<0 or denominator<=0:
                    raise ValueError('Invalid allegedly qualified relative-volume transfer')
                q=q0*mn/denominator
                n=float(row.total_gfa_m2)*q;r=float(row.total_gfa_m2)-n
                result.loc[index,['residential_gfa_m2','non_residential_gfa_m2']]=[r,n]
                used=True;role='2020_preserving_relative_GHSL_sector_volume_change'
            elif not qualified_anchor:
                role='retained_missing_or_unsupported_baseline_level_or_composition'
            elif source is not None and source.source_path_role=='zero_2020_component_prevents_relative_transfer':
                role='retained_v16_zero_source_reference_component_not_epsilon_filled'
            result.loc[index,'dynamic_composition_used']=used
            result.loc[index,'composition_update_role']=role
            result.loc[index,'composition_temporal_role']=source.temporal_role if source is not None else 'missing_source'
            result.loc[index,'source_nonres_volume_share']=source.source_nonres_share if source is not None else np.nan
            result.loc[index,'composition_source_resolution_m']=source.source_resolution_m if source is not None else np.nan
        selected=result.country_id.eq(country)
        ordered=result.loc[selected].sort_values('year')
        for sector in ['residential','non_residential']:
            col=sector+'_gfa_m2';normalizer=r0 if sector=='residential' else n0
            result.loc[ordered.index,sector+'_ratio_to_2020']=ordered[col]/normalizer if normalizer>0 else np.nan
            result.loc[ordered.index,sector+'_annual_net_change_m2']=ordered[col].diff()
    result['nonres_gfa_allocation_share']=result.non_residential_gfa_m2/result.total_gfa_m2
    result['composition_change_from_v16_pp']=100*(result.nonres_gfa_allocation_share-result.retained_v16_nonres_share)
    result['accounting_residual_m2']=result.residential_gfa_m2+result.non_residential_gfa_m2-result.total_gfa_m2
    result['composition_source_role']='predominant_use_volume_transfer_not_observed_floor_function'
    result['composition_validated']=False
    result['floor_area_composition_validated']=False
    result['default_changed']=False
    result['original_model_version']=result.get('model_version','v16')
    result['model_version']=VERSION
    result['new_composition_fitted_parameters']=0
    np.testing.assert_array_equal(result.total_gfa_m2.to_numpy(),original.total_gfa_m2.to_numpy())
    rows=result.year.eq(2020)
    for col in ['total_gfa_m2','residential_gfa_m2','non_residential_gfa_m2']:
        np.testing.assert_array_equal(result.loc[rows,col].to_numpy(),original.loc[rows,col].to_numpy())
    return result
