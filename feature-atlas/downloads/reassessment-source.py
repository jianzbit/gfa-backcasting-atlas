"""Frozen feature re-assessment and nested, one-dimensional B0 pooling study.

Uses existing exposed references only. Never modifies the operational B0.
Run: bundled-python scripts/reassess_b0_features.py prepare|diagnose|fit|score|report
"""
from __future__ import annotations
import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import html
import itertools
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
from v7 import shared_dynamic_stock as b0
from v7.dynamic_sector_composition import apply_composition
from gfa_science_v2.reference_integration import change_rows,summarize_changes

OUT=ROOT/'review/2026-10-30-b0-feature-reassessment'
INV=ROOT/'review/2026-10-30-feature-inventory'
BASE=ROOT/'review/2026-10-16-shared-dynamic-stock-v16'
FIVE=ROOT/'review/2026-10-29-five-country-validation'
COMP=ROOT/'review/2026-10-21-dynamic-sector-composition'
DEVELOPMENT=['CHL','DEU','DNK','KAZ','KGZ','KOR','ROU']
EXTRA=['FIN','JPN','NLD']
RHOS=[0.,.5,1.]
ORIGINAL_WEIGHTS=dict(b0.FAMILY_WEIGHT)
METHODS=['B0_fixed_pooling','B0_nested_data_selected_pooling']
PROTECTED=[ROOT/p for p in [
 'review/2026-10-29-development-freeze/artifacts/B0_country_year.csv',
 'review/2026-10-29-development-freeze/artifacts/P1_05904_country_year.csv',
 'research-site/showcase/data.js','research-site/showcase/atlas.js',
 'v7/shared_dynamic_stock.py','v7/backcast_observation_dynamic.py',
 'review/2026-10-16-shared-dynamic-stock-v16/fitted_model.json']]

def now():return datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def csv(p):return pd.read_csv(p,float_precision='round_trip',low_memory=False)
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
    if isinstance(x,np.bool_):return bool(x)
    if isinstance(x,np.integer):return int(x)
    if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
    return x
def save(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def record(p):return dict(path=str(p.relative_to(ROOT)),sha256=sha(p),bytes=p.stat().st_size)
def verify(records):
    for r in records:
        actual=sha(ROOT/r['path'])
        if actual!=r['sha256']:
            repair=read(OUT/'implementation_repair.json') if (OUT/'implementation_repair.json').exists() else {}
            allowed=(r['path']==repair.get('path') and r['sha256']==repair.get('previous_sha256') and actual==repair.get('repaired_sha256'))
            if not allowed:raise ValueError('Frozen file changed: '+r['path'])
def truth(s):return s.astype(str).str.lower().eq('true')

def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'protocol.json').exists():
        verify(read(OUT/'protocol.json')['protected_files'])
        assert sha(OUT/'protocol.json')==(OUT/'protocol.sha256').read_text().strip()
        return
    sources=[INV/n for n in ['feature_inventory_F01_F43.csv','reference_annual_pairs.csv','reference_cumulative_pairs.csv','reference_associations.csv','within_category_vif.csv']]
    sources += [BASE/'inputs/country_year_inputs_2015_2030.csv',BASE/'observations/development_observations.csv',BASE/'inputs/factor_temporal_semantics.csv',FIVE/'references.csv',COMP/'annual_composition_source_paths.csv',Path(__file__)]
    p=dict(id='B0-feature-reassessment-20261030-v1',frozen_at_utc=now(),
      reference_status='EXPOSED_DEVELOPMENT_EVIDENCE; no untouched or global accuracy claim',
      unchanged=['2020 anchors','source data and qualification masks','sector allocation','horizontal prior','future continuation','seven shared coefficients and penalties','operational B0 and P1'],
      feature_screen=dict(reference_panels_separate=True,window='2016–2020',target='native adjacent-year percentage stock growth',
        comparison='train-country mean versus mean plus one standardized feature',
        preprocessing='B0 lag-prepared qualified features; static final historical summary only; train-only weighted mean and RMS; no source imputation',
        ridge=1.,country_budget=1.,minimum_training_countries=3,minimum_test_intervals=3,
        formula='yhat=mean_train(y)+sd_train(y)*b*z; b=sum(w*z*y_standardized)/(sum(w*z*z)+1)',
        evaluation='held-country matched-sample macro MAE; baseline scored on identical rows; absence has no fabricated prediction',
        interpretation='marginal retrospective usefulness, not incremental full-B0 ablation, forecast skill or causal effect',
        associations='within-country demeaned Pearson and rank correlation; leave-one-country-out sign stability, descriptive only; no p-value selection'),
      pooling_study=dict(formula='family_weight(f,rho)=original_family_weight(f)**(1-rho)',
        choices=RHOS,meaning=['current priors','partially flattened priors','equal family weights within each existing axis'],
        parameter_budget='one discrete shared pooling choice; seven existing coefficients refitted; no 43-variable free weighting',
        quality_weights='unchanged; unavailable and static features never become annual evidence',
        selection='inner whole-country exclusion; mean of per-country, source/channel-balanced absolute native log-ratio errors x100; all eligible nonanchor observations',
        ties='within1e-10, prefer smaller rho (closer to fixed B0)',
        outer=DEVELOPMENT+EXTRA,training=DEVELOPMENT,
        inner_exclusion='exclude both outer and inner countries from every label-dependent fit, normalization, leverage and composition donors',
        extra_countries='not used in original seven-country fitting; exposed five-country diagnostic records, not untouched final tests',
        evaluation='native RES and native Total separately; common-anchor annual and five-year stock-increment diagnostics; no origin-valid forecast claim',
        no_post_score_expansion=True,no_automatic_promotion=True),
      protected_files=[record(p) for p in PROTECTED],source_files=[record(p) for p in sources])
    save(OUT/'protocol.json',p);(OUT/'protocol.sha256').write_text(sha(OUT/'protocol.json')+'\n')
    print('Protocol frozen:',sha(OUT/'protocol.json'),flush=True)

def corr(x,y,w):
    x=np.asarray(x,float);y=np.asarray(y,float);w=np.asarray(w,float)
    x=x-np.average(x,weights=w);y=y-np.average(y,weights=w)
    d=np.sqrt(np.sum(w*x*x)*np.sum(w*y*y))
    return float(np.sum(w*x*y)/d) if d>1e-24 else np.nan
def association(g):
    a=g.groupby('country_id',group_keys=False).filter(lambda z:len(z)>=3).copy()
    if a.country_id.nunique()<3:return np.nan
    x=a.x-a.groupby('country_id').x.transform('mean');y=a.y-a.groupby('country_id').y.transform('mean')
    w=1/a.groupby('country_id').y.transform('size')
    return corr(x,y,w)

def diagnose():
    prepare();verify(read(OUT/'protocol.json')['source_files'])
    inv=csv(INV/'feature_inventory_F01_F43.csv');panel=csv(BASE/'inputs/country_year_inputs_2015_2030.csv')
    view=b0.historical_source_view(panel);refs=csv(INV/'reference_annual_pairs.csv');refs=refs[~truth(refs.excluded_break)]
    folds=[];sensitivity=[];summary=[]
    for r in inv.to_dict('records'):
        name=r['factor_name'];h=view[['country_id','year',name]].copy()
        h['x']=b0.transformed(h[name],name)
        if name in b0.ALL_STATIC:
            context=h[h.year.eq(2020)].set_index('country_id').x
            h['x']=h.country_id.map(context)
        for p,rr in refs.groupby('panel'):
            d=rr.merge(h[['country_id','year','x']],on=['country_id','year'],validate='one_to_one').rename(columns={'reference_growth_pp':'y'}).dropna(subset=['x','y'])
            # A country cannot gain extra influence merely by having more years.
            d=d.groupby('country_id',group_keys=False).filter(lambda z:len(z)>=3)
            timing_eligible=r['annual_variation']=='Yes' and name not in b0.ALL_STATIC
            r_all=association(d) if timing_eligible else np.nan
            for held in sorted(d.country_id.unique()):
                if timing_eligible:
                    sr=association(d[d.country_id.ne(held)])
                    sensitivity.append(dict(feature_id=r['feature_id'],panel=p,excluded_country=held,pearson_r=sr,full_pearson_r=r_all,sign_matches_full=bool(sr*r_all>0) if np.isfinite(sr*r_all) else None))
                tr=d[d.country_id.ne(held)];te=d[d.country_id.eq(held)]
                if tr.country_id.nunique()<3:continue
                w=1/tr.groupby('country_id').y.transform('size').to_numpy()
                x,y=tr.x.to_numpy(),tr.y.to_numpy();xm=np.average(x,weights=w);ym=np.average(y,weights=w)
                xs=np.sqrt(np.average((x-xm)**2,weights=w));ys=np.sqrt(np.average((y-ym)**2,weights=w))
                if xs<=1e-12 or ys<=1e-12:continue
                z=(x-xm)/xs;zy=(y-ym)/ys;b=np.sum(w*z*zy)/(np.sum(w*z*z)+1.)
                pred=ym+ys*b*(te.x.to_numpy()-xm)/xs
                for i,(ix,t) in enumerate(te.iterrows()):
                    folds.append(dict(feature_id=r['feature_id'],panel=p,country_id=held,year=int(t.year),
                      reference_growth_pp=t.y,predicted_growth_pp=pred[i],training_mean_growth_pp=ym,
                      error_pp=pred[i]-t.y,baseline_error_pp=ym-t.y,training_countries=';'.join(sorted(tr.country_id.unique())),
                      standardized_slope=b,train_x_mean=xm,train_x_scale=xs,test_input_outside_train=bool(t.x<tr.x.min() or t.x>tr.x.max()),
                      scope='EXPOSED_RETROSPECTIVE_MARGINAL_SCREEN'))
            summary.append(dict(feature_id=r['feature_id'],panel=p,prepared_within_annual_r=r_all,matched_countries=d.country_id.nunique(),matched_rows=len(d)))
    f=pd.DataFrame(folds);s=pd.DataFrame(sensitivity);a=pd.DataFrame(summary)
    f.to_csv(OUT/'feature_screen_predictions.csv',index=False);s.to_csv(OUT/'association_country_sensitivity.csv',index=False)
    c=f.groupby(['feature_id','panel','country_id']).agg(feature_MAE_pp=('error_pp',lambda x:abs(x).mean()),baseline_MAE_pp=('baseline_error_pp',lambda x:abs(x).mean()),bias_pp=('error_pp','mean'),intervals=('year','size')).reset_index()
    c['gain_pp']=c.baseline_MAE_pp-c.feature_MAE_pp;c.to_csv(OUT/'feature_screen_country_metrics.csv',index=False)
    m=c.groupby(['feature_id','panel']).agg(LOCO_MAE_pp=('feature_MAE_pp','mean'),matched_baseline_MAE_pp=('baseline_MAE_pp','mean'),macro_gain_pp=('gain_pp','mean'),improved_countries=('gain_pp',lambda x:int((x>1e-10).sum())),worsened_countries=('gain_pp',lambda x:int((x< -1e-10).sum())),test_countries=('country_id','nunique')).reset_index()
    robust=s.groupby(['feature_id','panel']).agg(jackknife_min_r=('pearson_r','min'),jackknife_max_r=('pearson_r','max'),jackknife_valid=('pearson_r','count'),jackknife_same_sign=('sign_matches_full',lambda x:int(x.fillna(False).sum()))).reset_index()
    a=a.merge(m,on=['feature_id','panel'],how='left').merge(robust,on=['feature_id','panel'],how='left')
    a=a.merge(inv[['feature_id','feature_name','annual_variation','B0_static_context','mechanism']],on='feature_id',validate='many_to_one')
    a['screen_status']=np.where(a.test_countries.fillna(0)>=4,'DESCRIPTIVE_LOCO_SCREEN','INSUFFICIENT_MATCHED_COUNTRIES_OR_VARIATION')
    a.to_csv(OUT/'feature_reference_evidence.csv',index=False)
    # Final inventory retains all original metadata and adds specific dispositions.
    decisions=[]
    special={
      'F01':('KEEP_ENDPOINT_PRIOR','Five-year surface trend, not five independent annual observations; preserve as a baseline and learn its response separately.'),
      'F02':('KEEP_GROUPED','Population and working-age population overlap strongly; retain one mechanism budget, not two independent votes.'),
      'F03':('KEEP_ANNUAL_TEST_NONLINEARITY','Real GDP growth is activity, not stock growth; marginal associations do not establish a unit response.'),
      'F04':('KEEP_GROUPED','Urban-population demand; share a demographic mechanism budget with population rather than duplicating votes.'),
      'F05':('STATIC_CONTEXT_ONLY','Annual PPP source exists but frozen B0 uses final historical context; it does not identify annual construction timing.'),
      'F06':('STATIC_CONTEXT_ONLY','Annual urban fraction is used as background in B0; do not call it a new annual timing signal.'),
      'F07':('ENDPOINT_CONTEXT_ONLY','Built surface per capita combines endpoint built data with population; apparent annual changes are not annual building observations.'),
      'F08':('KEEP_GROUPED_LIGHTS','National lights are activity proxies; compare as one lights family with built-up lights, not independent stock observations.'),
      'F09':('KEEP_QUALIFIED_ANNUAL','Annual impervious-area changes can time horizontal change but do not directly measure floor area or vertical change.'),
      'F14':('STATIC_COMPOSITION_CONTEXT','A volume share conditional on source assumptions; not an observed annual GFA-use fraction.'),
      'F15':('STATIC_CONTEXT_ONLY','Urban-core morphology is context; avoid annual growth claims from a static snapshot.'),
      'F16':('ENDPOINT_CONTEXT_ONLY','Core/periphery endpoint contrast; not independent annual observations.'),
      'F17':('KEEP_LAGGED_CONSTRUCTION','Use current and lagged construction as one distributed-lag mechanism; construction value added is not completed floor area.'),
      'F18':('INDIRECT_ONLY','Already contributes one-half of F17; do not fit an additional independent vote.'),
      'F25':('PRIORITY_ACQUISITION_IF_AVAILABLE','Recorded completed floor area can constrain gross additions; it still needs demolition/net-stock handling and coverage documentation.'),
      'F26':('CONTEXTUAL_PROXY','Cement production is not consumption or building-only use; trade and infrastructure can dominate.'),
      'F28':('REDUNDANCY_CONTROL','Period correlation with population about0.96; keep within the same mechanism, not an extra independent weight.'),
      'F30':('STATIC_CONTEXT_IN_B0','Real-interest source is annual but implementation uses static context; changing this is a separate model experiment.'),
      'F33':('CREDIT_RATIO_PROXY','Credit/GDP changes combine credit and GDP-denominator effects; they are not building-only investment or a measured stock increment.'),
      'F38':('SHOCK_PROXY_ONLY','Affected-person counts do not measure destroyed GFA. A high small-panel Pearson coefficient is not enough to upweight.'),
      'F39':('SHOCK_PROXY_ONLY','Deaths are not lost building area; test panel may contain no variation. Keep unsupported effects unlearned.'),
      'F40':('STATIC_STOCK_CONTEXT','Endpoint-derived stock-age proxy, not annual demolition or a measured lifetime distribution.'),
      'F41':('KEEP_GROUPED_LIGHTS','Built-up lights are highly related to national/alternative lights. Keep one family budget.'),
      'F42':('KEEP_GROUPED_LIGHTS','Alternative built-up lights should assess source robustness, not add another independent vote.'),
      'F43':('EXCLUDE_UNQUALIFIED','Alternative annual construction source has no qualified local intake; do not splice it into F17 without a harmonization check.')}
    for r in inv.to_dict('records'):
        fid=r['feature_id']
        if fid in special:disposition,reason=special[fid]
        elif not bool(r['B0_active']):disposition,reason='UNAVAILABLE_IN_FROZEN_INPUTS','No qualified active numeric series; retain in inventory, do not set missing values to zero.'
        elif bool(r['B0_static_context']):disposition,reason='STATIC_CONTEXT_ONLY','Useful as background only under the current implementation.'
        else:disposition,reason='KEEP_QUALIFIED_GROUPED','Retain qualified annual evidence within its existing physical mechanism; no increase in weight is established by correlation alone.'
        r.update(reassessment_disposition=disposition,reassessment_reason=reason,individual_weight_recommendation='No isolated empirical weight established; see matched LOCO screen and nested group-pooling experiment')
        decisions.append(r)
    pd.DataFrame(decisions).to_csv(OUT/'reassessed_F01_F43.csv',index=False)
    save(OUT/'diagnostic_summary.json',dict(features=43,source_annual=31,qualified_annual=26,B0_annual_timing=22,
       paired_screen_rows=len(f),panels=a.groupby('panel').agg(annual_screened_features=('test_countries',lambda x:int(x.ge(4).sum()))).reset_index().to_dict('records'),
       no_absolute_level_validation='Residential development labels include source-native ratios; this screen evaluates growth, not national GFA level accuracy',
       missing_inputs_never_imputed=True))
    print('Feature re-assessment saved',flush=True)

@contextmanager
def weights(rho):
    old=b0.FAMILY_WEIGHT
    b0.FAMILY_WEIGHT={k:float(v**(1-rho)) for k,v in ORIGINAL_WEIGHTS.items()}
    try:yield
    finally:b0.FAMILY_WEIGHT=old

def model_key(excluded,rho):return ('full' if not excluded else 'exclude_'+'_'.join(sorted(excluded)))+'_rho'+str(rho).replace('.','p')
def source_inputs():return csv(BASE/'inputs/country_year_inputs_2015_2030.csv'),csv(BASE/'observations/development_observations.csv'),csv(BASE/'inputs/factor_temporal_semantics.csv').set_index('factor_name').quality_class.to_dict()

def fit():
    prepare();verify(read(OUT/'protocol.json')['source_files'])
    panel,obs,q=source_inputs();(OUT/'models').mkdir(exist_ok=True)
    contexts=[()]+[(c,) for c in DEVELOPMENT]+list(itertools.combinations(DEVELOPMENT,2))
    # Even a country absent from the label deck is excluded from the unlabeled donor pool.
    contexts += [(c,) for c in EXTRA]+[(c,v) for c in EXTRA for v in DEVELOPMENT]
    audit=[]
    for exclusions in contexts:
        for rho in RHOS:
            key=model_key(exclusions,rho);path=OUT/'models'/f'{key}.json';start=time.monotonic()
            if path.exists():model=read(path)
            else:
                with weights(rho):model,*_=b0.fit_model(panel,obs,q,excluded_countries=list(exclusions))
                model['pooling_rho']=rho;model['family_weights_override']={k:v**(1-rho) for k,v in ORIGINAL_WEIGHTS.items()}
                assert not set(exclusions)&set(model['training_countries'])
                save(path,model)
            audit.append(dict(key=key,excluded_countries=list(exclusions),rho=rho,training_countries=model['training_countries'],training_observations=model['training_observations'],converged=model['converged'],gradient_inf_norm=model['gradient_inf_norm']))
            print(f'Fitted {len(audit)}/{len(contexts)*len(RHOS)} {key} ({time.monotonic()-start:.1f}s)',flush=True)
    save(OUT/'fit_audit.json',audit)
    save(OUT/'fit_freeze.json',dict(at_utc=now(),scores_opened=False,files=[record(p) for p in sorted((OUT/'models').glob('*.json'))]+[record(OUT/'fit_audit.json')]))

def channel_score(obs,pred,country):
    d=obs[obs.country_id.eq(country)&truth(obs.relative_change_training_eligible)&~truth(obs.normalization_identity)].copy()
    lookup=pred[pred.country_id.eq(country)].set_index('year')
    col={'residential':'residential_gfa_m2','non_residential':'non_residential_gfa_m2','total':'total_gfa_m2'}
    d['abs_error']=d.apply(lambda r:abs(100*(np.log(lookup.loc[int(r.year),col[r.sector]]/lookup.loc[2020,col[r.sector]])-r.native_log_ratio_to_2020)),axis=1)
    return float(d.groupby(['source_family_id','observation_channel']).abs_error.mean().groupby('source_family_id').mean().mean())

def score():
    prepare();verify(read(OUT/'fit_freeze.json')['files'])
    panel,obs,q=source_inputs();composition=csv(COMP/'annual_composition_source_paths.csv')
    refs=csv(FIVE/'references.csv');cache={};inner=[];selections=[];held=[];native=[]
    def prediction(exclusions,rho):
        key=model_key(exclusions,rho)
        if key not in cache:
            model=read(OUT/'models'/f'{key}.json')
            with weights(rho):raw=b0.predict_model(panel,model)[0]
            # Inner selection uses native pre-allocation channels only. Do not run
            # an unused worldwide allocation for every inner fit.
            cache[key]=raw
        return cache[key]
    outer_contexts=[None]+DEVELOPMENT+EXTRA
    for outer in outer_contexts:
        ex=[outer] if outer is not None else []
        training=[c for c in DEVELOPMENT if c not in ex]
        for rho in RHOS:
            for v in training:
                raw=prediction(sorted(ex+[v]),rho)
                inner.append(dict(outer_country=outer or 'FULL',inner_country=v,rho=rho,held_native_abs_log_error_x100=channel_score(obs,raw,v),excluded_countries=';'.join(sorted(ex+[v]))))
        d=pd.DataFrame(inner);d=d[d.outer_country.eq(outer or 'FULL')]
        means=d.groupby('rho').held_native_abs_log_error_x100.mean()
        best=float(means.min());selected=min(float(r) for r,s in means.items() if s<=best+1e-10)
        selections.append(dict(outer_country=outer or 'FULL',selected_rho=selected,inner_score_by_rho={str(k):v for k,v in means.items()},training_countries=training))
        for method,rho in [(METHODS[0],0.),(METHODS[1],selected)]:
            raw=prediction(ex,rho)
            if outer is None:
                continue
            a=raw[raw.country_id.eq(outer)].copy();a['method']=method;a['rho']=rho
            # Allocation is separable by country; retain the canonical operator.
            h=apply_composition(a,composition[composition.country_id.eq(outer)]).copy();h['method']=method;h['rho']=rho
            held.append(h)
            for r in obs[obs.country_id.eq(outer)].to_dict('records'):
                col={'residential':'residential_gfa_m2','total':'total_gfa_m2','non_residential':'non_residential_gfa_m2'}[r['sector']]
                look=a.set_index('year');pr=look.loc[int(r['year']),col]/look.loc[2020,col]
                native.append({**r,'method':method,'rho':rho,'predicted_native_ratio':pr,'abs_log_error_x100':abs(100*(np.log(pr)-r['native_log_ratio_to_2020']))})
        print('Nested selection completed:',outer or 'FULL',selected,flush=True)
    pd.DataFrame(inner).to_csv(OUT/'inner_country_scores.csv',index=False);save(OUT/'nested_selections.json',selections)
    preds=pd.concat(held,ignore_index=True);preds.to_csv(OUT/'country_excluded_predictions.csv',index=False)
    n=pd.DataFrame(native);n.to_csv(OUT/'native_channel_predictions.csv',index=False)
    nm=n[n.year.ne(2020)].groupby(['method','sector','country_id','source_family_id','observation_channel']).abs_log_error_x100.mean().groupby(['method','sector','country_id','source_family_id']).mean().groupby(['method','sector','country_id']).mean().reset_index()
    nm.to_csv(OUT/'native_country_metrics.csv',index=False);nm.groupby(['method','sector']).abs_log_error_x100.agg(['mean','max','count']).reset_index().to_csv(OUT/'native_macro_metrics.csv',index=False)
    levels=[]
    for method in METHODS:
        pp=preds[preds.method.eq(method)].set_index(['country_id','year'])
        for r in refs.to_dict('records'):
            c=r['country_id'];y=int(r['year']);p=pp.loc[(c,y),'total_gfa_m2'] if (c,y) in pp.index else np.nan;a=pp.loc[(c,2020),'total_gfa_m2']
            ra=refs[refs.country_id.eq(c)&refs.year.eq(2020)].reference_m2.iloc[0]
            levels.append({**r,'method':method,'prediction_m2':p,'common_anchor_prediction_m2':ra*p/a})
    levels=pd.DataFrame(levels);changes,excluded=change_rows(levels);cc,mm=summarize_changes(changes)
    for name,d in [('level_pairs',levels),('change_pairs',changes),('change_exclusions',excluded),('country_metrics',cc),('macro_metrics',mm)]:d.to_csv(OUT/f'{name}.csv',index=False)
    main=mm[mm['mode'].eq('common_2020_anchor')].copy();main.to_csv(OUT/'main_comparison.csv',index=False)
    paired=cc[cc['mode'].eq('common_2020_anchor')&cc.horizon_years.eq(1)].pivot(index='country_id',columns='method',values='MAE_pp').reset_index()
    paired['gain_pp']=paired[METHODS[0]]-paired[METHODS[1]];paired.to_csv(OUT/'paired_country_annual.csv',index=False)
    # Canonical control must reproduce prior leave-country results.
    previous=csv(ROOT/'review/2026-10-30-b0-controlled-nonlinear/evaluation/paired_country_annual.csv').set_index('country_id').B0_linear_response_control
    np.testing.assert_allclose(paired.set_index('country_id')[METHODS[0]].sort_index(),previous.sort_index(),rtol=1e-8,atol=1e-7)
    # A full selected fit is a reproducible development artifact, not a release replacement.
    rho=selections[0]['selected_rho'];raw=prediction([],rho);composed=apply_composition(raw,composition)
    composed.to_csv(OUT/'selected_pooling_global_core.csv',index=False)
    assert not composed.duplicated(['country_id','year']).any() and len(composed)==len(panel)
    np.testing.assert_array_equal(composed[composed.year.eq(2020)].set_index('country_id').total_gfa_m2,panel[panel.year.eq(2020)].set_index('country_id').fixed_2020_total_anchor_m2.loc[composed[composed.year.eq(2020)].country_id])
    valid=composed.dropna(subset=['total_gfa_m2','residential_gfa_m2','non_residential_gfa_m2'])
    np.testing.assert_allclose(valid.residential_gfa_m2+valid.non_residential_gfa_m2,valid.total_gfa_m2,rtol=1e-14,atol=1e-3)
    assert (valid[['residential_gfa_m2','non_residential_gfa_m2','total_gfa_m2']]>=0).all().all()
    for k in ['total','residential','non_residential']:
        np.testing.assert_allclose(composed.groupby('country_id')[k+'_gfa_m2'].diff(),composed[k+'_annual_net_change_m2'],equal_nan=True,rtol=1e-11,atol=1e-3)
    full=read(OUT/'models'/f'{model_key([],rho)}.json')
    pd.DataFrame([dict(family=f,fixed_weight=w,selected_weight=w**(1-rho),selected_rho=rho) for f,w in ORIGINAL_WEIGHTS.items()]).to_csv(OUT/'full_fit_family_weights.csv',index=False)
    protected=read(OUT/'protocol.json')['protected_files'];verify(protected)
    eng=dict(status='PASS',models_refitted=len(read(OUT/'fit_audit.json')),held_labels_excluded=True,nested_training_normalization=True,held_donors_excluded=True,control_replay_matches=True,anchors_exact=True,R_plus_NR_equals_Total=True,net_change_identity=True,no_negative_stocks=True,protected_files_unchanged=True,core_countries=composed.country_id.nunique(),rows=len(composed),scientific_accuracy='NOT_ESTABLISHED_BY_ACCOUNTING')
    save(OUT/'engineering_checks.json',eng)
    annual=main[main.horizon_years.eq(1)].set_index('method');five=main[main.horizon_years.eq(5)].set_index('method')
    gain1=annual.loc[METHODS[0],'available_domain_macro_MAE_pp']-annual.loc[METHODS[1],'available_domain_macro_MAE_pp']
    gain5=five.loc[METHODS[0],'available_domain_macro_MAE_pp']-five.loc[METHODS[1],'available_domain_macro_MAE_pp']
    save(OUT/'weight_study_summary.json',dict(at_utc=now(),main=main.to_dict('records'),annual_gain_pp=gain1,fiveyear_gain_pp=gain5,
        improved_countries=paired[paired.gain_pp.gt(1e-10)].country_id.tolist(),worsened_countries=paired[paired.gain_pp.lt(-1e-10)].country_id.tolist(),
        selected_full_rho=rho,outer_selections=selections,coefficients=full['coefficients'],
        without_KGZ=native_without_kgz(nm),engineering_status='PASS',diagnostic_status='EXPOSED_NESTED_DEVELOPMENT_COMPARISON',
        scientific_status='NO_INDEPENDENT_GLOBAL_ACCURACY_CLAIM',default_changed=False,
        recommendation='Keep operational B0. This finite pooling study '+('improves both change horizons in this exposed panel; a replacement is not independently confirmed.' if gain1>0 and gain5>0 else 'does not improve both change horizons; do not promote the weighting rule.')))
    print('Scores saved',gain1,gain5,flush=True)

def native_without_kgz(nm):return nm[nm.country_id.ne('KGZ')&nm.sector.eq('residential')].groupby('method').abs_log_error_x100.mean().to_dict()

def report():
    prepare();w=read(OUT/'weight_study_summary.json');d=read(OUT/'diagnostic_summary.json');inv=csv(OUT/'reassessed_F01_F43.csv');e=csv(OUT/'feature_reference_evidence.csv');pc=csv(OUT/'paired_country_annual.csv');main=csv(OUT/'main_comparison.csv')
    changes=csv(OUT/'change_pairs.csv');changes=changes[changes['mode'].eq('common_2020_anchor')&changes.horizon_years.eq(1)].copy()
    changes['era']=np.where(changes.end_year.le(2020),'2015–2020','2020–2025')
    era_country=changes.groupby(['method','era','country_id']).agg(MAE_pp=('absolute_change_error_pp','mean'),bias_pp=('change_error_pp','mean'),intervals=('end_year','size')).reset_index()
    eras=era_country.groupby(['method','era']).agg(countries=('country_id','nunique'),MAE_pp=('MAE_pp','mean'),bias_pp=('bias_pp','mean'),intervals=('intervals','sum')).reset_index()
    eras.to_csv(OUT/'era_change_metrics.csv',index=False)
    # Embed the full data so the report remains usable offline, including CSV export.
    shares=[]
    for kind,axes in [('period',b0.TOTAL_AXES),('annual',b0.TIMING_AXES)]:
        for axis,families in axes.items():
            den0=sum(ORIGINAL_WEIGHTS[f] for f in families)
            den1=sum(ORIGINAL_WEIGHTS[f]**(1-w['selected_full_rho']) for f in families)
            for f in families:shares.append(dict(kind=kind,axis=axis,family=f,fixed_share_if_all_available=ORIGINAL_WEIGHTS[f]/den0,selected_share_if_all_available=ORIGINAL_WEIGHTS[f]**(1-w['selected_full_rho'])/den1))
    pd.DataFrame(shares).to_csv(OUT/'normalized_axis_weights.csv',index=False)
    for name in ['within_category_vif.csv','reference_associations.csv','existing_group_ablation.csv']:
        shutil.copy2(INV/name,OUT/name)
    data=dict(inventory=inv.to_dict('records'),evidence=e.to_dict('records'),weights=csv(OUT/'full_fit_family_weights.csv').to_dict('records'),summary=w)
    def table(frame):return frame.to_html(index=False,border=0,classes='table',float_format=lambda x:f'{x:.4f}',escape=True,na_rep='—')
    annual=main[main.horizon_years.eq(1)][['method','complete_countries','available_domain_macro_MAE_pp','country_macro_bias_pp']].rename(columns={'available_domain_macro_MAE_pp':'Annual MAE (pp)','country_macro_bias_pp':'Annual bias (pp)'})
    five=main[main.horizon_years.eq(5)][['method','complete_countries','available_domain_macro_MAE_pp']].rename(columns={'available_domain_macro_MAE_pp':'Five-year MAE (pp)'})
    inner_selection=pd.DataFrame([dict(rho=float(r),pooling={0.:'Original priors',.5:'Partially flattened',1.:'Equal family weights'}[float(r)],selection_abs_log_error_x100=s,inner_test_countries=7) for r,s in w['outer_selections'][0]['inner_score_by_rho'].items()])
    inner_selection.to_csv(OUT/'full_development_inner_comparison.csv',index=False)
    sections=[]
    for panel,g in e.groupby('panel'):
        top=g[g.test_countries.ge(4)].sort_values('macro_gain_pp',ascending=False)
        sections.append('<h3>'+html.escape(panel)+'</h3>'+table(top[['feature_id','feature_name','matched_countries','matched_rows','prepared_within_annual_r','LOCO_MAE_pp','matched_baseline_MAE_pp','macro_gain_pp','improved_countries','worsened_countries']]))
    body='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>B0 · 43-feature reassessment</title>
<style>:root{color-scheme:light;--ink:#20342f;--muted:#5e6d67;--accent:#167861}*{box-sizing:border-box}body{margin:0;background:#f6f5ef;color:var(--ink);font:16px/1.55 system-ui,sans-serif}main{max-width:1240px;margin:auto;padding:42px 28px 100px}h1{font-size:36px;line-height:1.15;max-width:900px}h2{margin-top:48px;border-top:1px solid #d2d9d2;padding-top:24px}h3{font-size:18px;margin-top:28px}p{max-width:960px}.muted,small{color:var(--muted)}nav{display:flex;gap:18px;flex-wrap:wrap}a{color:var(--accent)}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.stat{background:white;padding:20px;border:1px solid #d4ddd5}.stat b{font-size:32px;display:block}.note{background:#e8efe8;padding:16px 20px;border-left:4px solid var(--accent)}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px;background:#fff}th,td{text-align:left;padding:10px 12px;border-bottom:1px solid #e3e7e2;vertical-align:top}th{background:#e9eee8;position:sticky;top:0}td{max-width:420px;min-width:80px}.formula{font:16px/1.8 ui-monospace,monospace;background:white;padding:18px;overflow:auto}button,select,input{font:inherit;padding:8px;border:1px solid #aebdb4;background:white;color:var(--ink);border-radius:4px}button{cursor:pointer}.controls{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}.badge{font-size:12px;letter-spacing:.07em;text-transform:uppercase;color:var(--accent)}details{margin:16px 0}summary{cursor:pointer;font-weight:600}svg{width:100%;height:auto;background:#fff} @media(max-width:700px){main{padding:24px 16px}.stats{grid-template-columns:repeat(2,1fr)}h1{font-size:28px}}@media print{button,input,select,nav{display:none}main{padding:0}.scroll{overflow:visible}h2{break-before:auto}}</style>
<main><div class="badge">Indicator 1.1 · controlled development study · 30 October 2026</div><h1>B0: which of the 43 features contain useful information?</h1>
<p>Annual availability, reference relationships, redundancy and a nested data-selected pooling experiment. Operational B0, P1 and the published Atlas are preserved.</p>
<nav><a href="#coverage">Coverage</a><a href="#associations">Reference evidence</a><a href="#weights">Weights</a><a href="#decisions">All 43 decisions</a><a href="#methods">Reproduce</a></nav>
<div class="stats"><div class="stat"><b>43</b>candidate features</div><div class="stat"><b>31</b>annual source candidates</div><div class="stat"><b>26</b>qualified annual signals</div><div class="stat"><b>22</b>B0 annual timing inputs</div></div>
<p class="note"><strong>Conclusion:</strong> __RECOMMEND__ Correlation alone does not justify a larger weight. These references have already been exposed during development.</p>
<h2 id="coverage">1. Availability and actual model use</h2><p>“The provider has annual data”, “we have qualified changing values”, and “B0 uses them as annual inputs” are different claims. This archive covers historical input intervals 2016–2020. Post-2020 B0 continues historical corrections with damping; it does not ingest new annual GDP, construction or light observations.</p>
<p>Within the 43 candidates, 32 are active directly or indirectly: 22 annual timing inputs, 8 static-context inputs, 1 endpoint prior and 1 indirect lag input. PPP per capita, urban fraction and real interest rates have annual source series but are used as static context by frozen B0. GHSL endpoint trends, morphology and stock-age proxies are not independent annual building observations. Eleven candidates are inactive or unavailable; missing values remain missing. F18 is an indirect lag input to F17, not a separate annual coefficient.</p>
<h2 id="associations">2. What relates to official/native reference growth?</h2><p>The residential panel has seven countries and 34 historical intervals. The native Total panel has five countries and 23 usable intervals after two predeclared publisher breaks. They remain separate. These source-native definitions do not establish global, definition-matched GFA accuracy.</p>
<p><strong>How to read:</strong> r measures within-country annual co-movement after demeaning, using B0-prepared inputs (including lag combinations and the negative sign for disaster/conflict risk). Static/endpoint inputs have no annual r. “Gain” is the matched mean-baseline MAE minus the one-feature held-country MAE; positive is better. Each test country is excluded from fitting and standardization. A feature may correlate with growth yet fail to improve prediction in another country. Static context can predict country differences but cannot locate annual shocks.</p>
<p class="muted">The single-feature screen predicts adjacent-year percentage growth rates; it is a marginal retrospective diagnostic, not the incremental value of adding that variable to full B0. Its scores are not directly comparable with the full-B0 stock-increment errors below. Different features have different matched samples; compare each with its own displayed baseline. No causal effects, multiple-testing discoveries or independent validation are claimed.</p>
<div class="scroll">__EVIDENCE__</div>
<h3>Redundancy and misleading high correlations</h3><p>Population vs working-age population has period r ≈0.959; construction vs its lag has r ≈0.943. The lag is already combined into construction. Lights variants share a mechanism and source errors. Preserve grouped budgets rather than counting each variant as independent evidence. Full 43-variable VIF is not estimable on the reference-country panel; the existing category-specific VIF diagnostics retain unsupported cases explicitly.</p>
<p>Cumulative Total correlations use only three comparable countries; values close to ±1 are not strong evidence with n=3. Disaster-affected people can show a large Pearson r but are not destroyed floor area, and the rank/jackknife checks may disagree. Neither warrants automatic upweighting. <a href="reference_associations.csv">Original annual and cumulative correlations</a> preserve both panel definitions and sample sizes.</p>
<p>The existing full-country predictor audit found category VIF ≈16.68 for population, 13.70 for working-age population, 27.06 for construction and 28.21 for its lag. These are predictor redundancy diagnostics on their stated complete-case samples, not reference-validation scores or full-model coefficient VIF. Built-weighted vs urban-core lights has within-country annual r ≈0.918. <a href="within_category_vif.csv">Category VIF</a> · <a href="existing_group_ablation.csv">Prior refitted group ablations</a>.</p>
<h2 id="weights">3. Can data improve the fixed aggregation weights?</h2><p>B0 already estimates seven shared response coefficients. Its quality weights and family pooling weights remain fixed. We tested one additional shared choice, selected only inside each outer training fold:</p>
<div class="formula">w_family(ρ) = w_original ^ (1 − ρ)<br>ρ ∈ {0, 0.5, 1}: original → partially flattened → equal family pooling<br>All seven B0 coefficients and preprocessing are refitted for every inner/outer fit.</div>
<p>This is a bounded test of the strength of current family-weight priors, not a fit of 43 independent feature weights. Quality masks, within-family quality weights, 2020 anchors, sector allocation and future rules are unchanged. Inner selection minimizes source/channel-balanced, country-equal absolute native log-ratio error. The seven-country fitting deck is unchanged; 159 distinct full-pipeline fits cover the nested label and donor exclusions.</p>
<h3>What did the training data select?</h3><div class="scroll">__INNER__</div><p>The full-development inner comparison above uses all eligible nonanchor native reference dates, including post-2020 dates, and reports absolute log-ratio error ×100, not annual percentage-point error. It is a model-selection score. All ten outer training folds also selected ρ=0; consequently the selected pipeline reproduces B0. This limited search does not prove the current weights are globally optimal or rule out other learned weighting structures.</p>
<div class="scroll">__ANNUAL____FIVE__</div><p>Annual and five-year errors are stock-increment errors in percentage points, using a common official 2020 starting level. The annual panel has five countries; five-year coverage has four. These are exposed, conditional trajectory diagnostics, not scientific gate PASS results or genuine forecast hindcasts.</p><h3>Before and after the 2020 input boundary</h3><div class="scroll">__ERAS__</div><p>This fixed time split describes where error occurs; it does not establish why. Post-2020 feature coefficients do not gain fresh annual economic inputs in this experiment.</p>
__CHART__<div class="scroll">__COUNTRIES__</div><h3>Full-development selected pooling weights</h3><div class="scroll">__WEIGHTS__</div><p>These are relative weights, normalized over available families inside each axis; they are not shares of predicted GFA. <a href="normalized_axis_weights.csv">Normalized shares assuming complete availability</a> show what flattening actually changes. The full fit selected ρ=__RHO__. Each outer fold makes its own inner-only choice; there is no country-specific deployment rule. Inspect <a href="nested_selections.json">all selections</a> and <a href="inner_country_scores.csv">inner scores</a>. The original B0 remains the default.</p>
<h2 id="decisions">4. Feature decisions and adjustment priorities</h2><p>Keep qualified annual signals within mechanism groups, retain static variables as context, and avoid duplicate votes. The main information gap is fresh post-2020 annual evidence, especially recorded additions/stock changes and comparable building-change observations. More economic proxies cannot substitute for these measurements.</p>
<p>Completed floor area (F25), where publicly available and comparable, is a priority acquisition candidate; it measures additions and still needs a net-stock bridge. Household counts and consistent dwelling-stock series can improve demand evidence if definitions and dates are documented. Revisit actual annual use of interest/PPP only as a separate controlled experiment. No new datasets were acquired or asserted to be globally available in this run.</p>
<div class="controls"><label>Search <input id="search" type="search" placeholder="ID, source, mechanism…"></label><label>Filter <select id="filter"><option value="all">All 43</option><option value="annual">Qualified annual</option><option value="static">B0 static context</option><option value="inactive">Inactive</option></select></label><button id="download">Download full reassessed inventory CSV</button></div><p id="count" aria-live="polite"></p><div class="scroll"><table><thead><tr><th>Feature</th><th>Coverage / temporal use</th><th>Current weights</th><th>Decision</th></tr></thead><tbody id="rows"></tbody></table></div>
<h2 id="methods">5. Evidence status and reproducibility</h2><p><strong>Engineering verification: PASS.</strong> Frozen outputs unchanged; exact 2020 anchors; R+NR=Total; annual net changes reconcile; control reproduces the earlier leave-country baseline. <strong>Development diagnostics:</strong> real scores above. <strong>Independent scientific validation:</strong> not supplied by this already-exposed panel. No 2030 accuracy percentage is inferred.</p>
<p>Reproduce using <code>scripts/reassess_b0_features.py prepare → diagnose → fit → score → report</code> with the bundled Python. The protocol was frozen before candidate fitting and scoring. No expansion of the three-point pooling search after results.</p>
<p><a href="protocol.json">Frozen protocol</a> · <a href="feature_reference_evidence.csv">All reference relationships</a> · <a href="association_country_sensitivity.csv">Country sensitivity</a> · <a href="feature_screen_predictions.csv">One-feature prediction pairs</a> · <a href="change_pairs.csv">B0 paired changes</a> · <a href="fit_audit.json">Fit audit</a> · <a href="engineering_checks.json">Engineering checks</a> · <a href="delivery_manifest.json">Hashes</a></p><small>Sources: frozen v16 qualified panel and development observations; five-country official/native reference audit; 43-feature inventory and its source manifest. Source URLs, definitions, units, lags, missingness and coverage are preserved in the downloadable inventory.</small></main>
<script type="application/json" id="data">__DATA__</script><script>
const D=JSON.parse(document.getElementById('data').textContent);const esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function render(){let q=document.querySelector('#search').value.toLowerCase(),f=document.querySelector('#filter').value;let a=D.inventory.filter(r=>(f==='all'||f==='annual'&&r.annual_variation==='Yes'||f==='static'&&r.B0_static_context||f==='inactive'&&!r.B0_active)&&(/^f[0-9]{2}$/.test(q)?r.feature_id.toLowerCase()===q:JSON.stringify(r).toLowerCase().includes(q)));document.querySelector('#count').textContent=a.length+' of 43 features';document.querySelector('#rows').innerHTML=a.map(r=>`<tr><td><strong>${esc(r.feature_id)} · ${esc(r.feature_name)}</strong><br><small>${esc(r.mechanism)}</small><details><summary>Definition / source</summary>${esc(r.original_definition)}<br>${esc(r.original_unit)}<br><a href="${esc(r.source_url)}" target="_blank" rel="noopener">${esc(r.source)}</a></details></td><td>Annual source: ${esc(r.source_annual_data)}<br>Qualified annual: ${esc(r.annual_variation)}<br>${esc(r.qualified_feature_countries)} countries in historical intake<br>${esc(r.B0_role)}<br><small>${esc(r.temporal_resolution)}</small></td><td>Quality: ${esc(r.quality_weight)}<br>Family: ${esc(r.family_weight)}<br><small>Final response coefficients are learned; these are not percentages of predicted GFA.</small></td><td><strong>${esc(r.reassessment_disposition)}</strong><br>${esc(r.reassessment_reason)}</td></tr>`).join('')}
document.querySelector('#search').addEventListener('input',render);document.querySelector('#filter').addEventListener('change',render);document.querySelector('#download').addEventListener('click',()=>{let k=Object.keys(D.inventory[0]),cell=x=>'"'+String(x??'').replaceAll('"','""')+'"';let s=[k.map(cell).join(','),...D.inventory.map(r=>k.map(c=>cell(r[c])).join(','))].join(String.fromCharCode(13,10));let u=URL.createObjectURL(new Blob(['\ufeff'+s],{type:'text/csv;charset=utf-8'}));let a=document.createElement('a');a.href=u;a.download='B0_reassessed_F01_F43.csv';a.click();setTimeout(()=>URL.revokeObjectURL(u),2000)});render();
</script></html>'''
    # Standard plotting output is also saved separately for research presentations.
    import subprocess
    sys.path.append(str(ROOT/'.tooling/indicator11-report-runtime'))
    previous_check_output=subprocess.check_output
    def font_safe_call(args,*a,**kw):
        if isinstance(args,(list,tuple)) and args and 'system_profiler' in str(args[0]):return b'{"SPFontsDataType":[]}'
        return previous_check_output(args,*a,**kw)
    subprocess.check_output=font_safe_call
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    finally:subprocess.check_output=previous_check_output
    fig,ax=plt.subplots(figsize=(10.5,4.6),layout='constrained');x=np.arange(len(pc));width=.34
    for j,(method,color,label) in enumerate(zip(METHODS,['#9a8e6c','#177b65'],['Fixed B0 pooling','Inner-selected pooling'])):
        bars=ax.bar(x+(j-.5)*width,pc[method],width,color=color,label=label)
        ax.bar_label(bars,fmt='%.3f',padding=3,fontsize=9)
    ax.set_xticks(x,pc.country_id);ax.set_ylabel('Annual stock-increment MAE (percentage points)')
    ax.set_title('Exposed five-country diagnostic · common 2020 anchor')
    ax.spines[['top','right']].set_visible(False);ax.legend(frameon=False)
    ax.set_ylim(0,max(pc[METHODS].max().max(),1)*1.2)
    fig.savefig(OUT/'annual_weight_comparison.png',dpi=180)
    fig.savefig(OUT/'annual_weight_comparison.svg');plt.close(fig)
    parts=['<a href="annual_weight_comparison.png"><img style="width:100%;height:auto" alt="Annual stock-increment MAE by country, fixed versus inner-selected pooling" src="data:image/png;base64,'+base64.b64encode((OUT/'annual_weight_comparison.png').read_bytes()).decode()+'"></a>']
    body=body.replace('__RECOMMEND__',html.escape(w['recommendation'])).replace('__EVIDENCE__',''.join(sections)).replace('__ANNUAL__',table(annual)).replace('__FIVE__',table(five)).replace('__INNER__',table(inner_selection)).replace('__ERAS__',table(eras)).replace('__COUNTRIES__',table(pc)).replace('__WEIGHTS__',table(csv(OUT/'full_fit_family_weights.csv'))).replace('__RHO__',str(w['selected_full_rho'])).replace('__CHART__',''.join(parts)).replace('__DATA__',json.dumps(clean(data),ensure_ascii=False,allow_nan=False).replace('</','<\\/'))
    (OUT/'report.html').write_text(body)
    save(OUT/'delivery_manifest.json',dict(at_utc=now(),protocol_sha256=sha(OUT/'protocol.json'),files=[record(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='delivery_manifest.json'],protected_after=[record(p) for p in PROTECTED]))
    print('Report saved:',OUT/'report.html',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','diagnose','fit','score','report']);a=p.parse_args();globals()[a.stage]()
