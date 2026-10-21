"""Adopt frozen GHSL sector allocation in the personal research Atlas.

User-selected conditional composition; not scientific approval or an accuracy
claim. Retains Total,2020components, source artifacts and all original exports.
"""
from __future__ import annotations
import hashlib,json,shutil,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
from scripts import build_country_explorer as legacy
from v7.dynamic_sector_composition import apply_composition
from v7 import final_gfa_release as accounting

SITE=ROOT/'research-site'
OUT=ROOT/'review/2026-10-21-dynamic-sector-atlas'
SOURCE=ROOT/'review/2026-10-21-dynamic-sector-composition'
OLD=ROOT/'review/2026-10-16-global-gfa-final'
VERSION='v16-ghsl-composition'
PREFIX=VERSION+'-'
LEVELS=accounting.LEVELS
CHANGES=accounting.CHANGES
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def rec(p):return dict(path=str(Path(p).relative_to(ROOT)),sha256=sha(p),bytes=Path(p).stat().st_size)
def save(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')

def freeze():
    OUT.mkdir(exist_ok=True)
    archive=SITE/'downloads/v16-atlas-before-ghsl-composition.zip'
    path=OUT/'adoption_protocol.json'
    if path.exists():
        data=json.loads(path.read_text())
        for r in data['immutable_inputs']:
            if sha(ROOT/r['path'])!=r['sha256']:raise ValueError('Immutable source changed')
        if sha(archive)!=data['previous_site_archive']['sha256']:raise ValueError('Old Atlas archive changed')
        return
    sources=[SOURCE/f for f in ['country_year_gfa_2015_2030_dynamic_composition.csv',
        'annual_composition_source_paths.csv','country_composition_coverage.csv',
        'native_epoch_country_volumes.csv','validation_summary.json','global_prediction_freeze.json',
        'validation_paired_comparison.csv','broad_native_interval_paired.csv','model_protocol.json']]
    sources += [OLD/'joint_country_year_scenario_paths.csv.gz',OLD/'country_year_gfa_2015_2030_final.csv',
        OLD/'world_gfa_2015_2030_final.csv',ROOT/'v7/dynamic_sector_composition.py',ROOT/'v7/shared_dynamic_stock.py']
    oldfiles=sorted(p for p in SITE.rglob('*') if p.is_file() and p!=archive)
    old_manifest=[rec(p) for p in oldfiles]
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in oldfiles:z.write(p,p.relative_to(SITE))
    save(path,dict(frozen_at_utc=now(),version=VERSION,
        authorization='User explicitly requested direct adoption of the four-epoch GHSL sector allocation in the personal Atlas.',
        purpose='Conditional research allocation; mixed validation retained, not an accuracy-upgrade claim',
        scientific_model_refits=0,new_fitted_parameters=0,
        rule='Use exactly the frozen2020-preserving relative-sector-volume allocation in qualified countries; retainv16 where unqualified or zero reference.',
        sensitivity='Apply the identical allocation to every one of37 coherent country-year scenarios using each scenario own2020sector shares. Aggregate countries within scenario before world min/max.',
        immutable_inputs=[rec(p) for p in sources],previous_site_archive=rec(archive),previous_site_files=old_manifest,
        original_research_outputs_overwritten=False,BIT_canonical_method_replaced=False))

def release():
    freeze()
    sources=pd.read_csv(SOURCE/'annual_composition_source_paths.csv',float_precision='round_trip')
    central=pd.read_csv(SOURCE/'country_year_gfa_2015_2030_dynamic_composition.csv',float_precision='round_trip',low_memory=False)
    old=pd.read_csv(OLD/'country_year_gfa_2015_2030_final.csv',float_precision='round_trip',low_memory=False)
    np.testing.assert_array_equal(central.total_gfa_m2,old.total_gfa_m2)
    np.testing.assert_array_equal(central[central.year.eq(2020)][LEVELS],old[old.year.eq(2020)][LEVELS])
    jointold=pd.read_csv(OLD/'joint_country_year_scenario_paths.csv.gz',float_precision='round_trip')
    paths=[]
    for scenario,g in jointold.groupby('scenario_id',sort=True):
        updated=apply_composition(g.reset_index(drop=True),sources)
        np.testing.assert_array_equal(updated.total_gfa_m2,g.total_gfa_m2)
        paths.append(updated[['scenario_id','country_id','year']+LEVELS+CHANGES])
        print('updated_sensitivity_allocation',scenario,flush=True)
    joint=pd.concat(paths,ignore_index=True).sort_values(['scenario_id','country_id','year'])
    accounting.assert_paths(joint,['scenario_id','country_id'])
    probe=joint[joint.scenario_id.eq('central_v16')].set_index(['country_id','year']).sort_index()
    actual=central.set_index(['country_id','year']).sort_index()
    np.testing.assert_array_equal(probe[LEVELS],actual[LEVELS])
    joint.to_csv(OUT/'joint_country_year_scenario_paths.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    central['release_version']=VERSION+'-20261021'
    central['adopted_atlas_composition']=True
    central['accuracy_improvement_established']=False
    central.to_csv(OUT/'country_year_gfa_2015_2030.csv',index=False)
    accounting.envelope(joint,['country_id','year']).to_csv(OUT/'country_year_scenario_envelopes.csv',index=False)
    world=accounting.world_paths(joint);world.to_csv(OUT/'world_joint_scenario_paths.csv',index=False)
    accounting.envelope(world,['cohort_id','year']).to_csv(OUT/'world_scenario_envelopes.csv',index=False)
    wc=world[world.scenario_id.eq('central_v16')].drop(columns='scenario_id').copy()
    originalworld=pd.read_csv(OLD/'world_gfa_2015_2030_final.csv',float_precision='round_trip')
    # Retain the already published Total text-level value for each coherent cohort.
    wc=wc.drop(columns=['total_gfa_m2','total_annual_net_change_m2']).merge(
        originalworld[['cohort_id','year','total_gfa_m2','total_annual_net_change_m2','estimate_phase','aggregate_role','absolute_accuracy_score_pct']],
        on=['cohort_id','year'],validate='one_to_one')
    np.testing.assert_allclose(wc.residential_gfa_m2+wc.non_residential_gfa_m2,wc.total_gfa_m2,rtol=2e-14,atol=1e-3)
    wc.to_csv(OUT/'world_gfa_2015_2030.csv',index=False)
    save(OUT/'release_checks.json',dict(country_year_rows=len(central),reporting_countries=central.country_id.nunique(),
        historical_dynamic_countries=191,future_dynamic_countries=189,scenario_count=joint.scenario_id.nunique(),
        scenario_country_year_rows=len(joint),all_country_Total_values_exactly_preserved=True,
        all_country_2020_triplets_exactly_preserved=True,all37_scenario_Total_paths_exactly_preserved=True,
        all37_scenario_2020_components_preserved=True,new_central_is_frozen_candidate_exact=True,
        sector_sensitivity_ranges_recomputed=True,global_ranges_from_coherent_scenario_sums=True,
        source_data_and_fitted_parameters_changed=False,legacy_snapshot_archived=True,
        adoption_is_not_accuracy_certification=True))

def export():
    # Reuse the existing exporter for unchanged factor roles and old downloads.
    legacy.main()
    p=SITE/'data/explorer-data.js';packet=json.loads(p.read_text().removeprefix('window.GFA_DATA=').rstrip(';\n'))
    rows=legacy.read(OUT/'country_year_gfa_2015_2030.csv')
    bounds={(r['country_id'],int(r['year'])):r for r in legacy.read(OUT/'country_year_scenario_envelopes.csv')}
    coverage={r['country_id']:r for r in legacy.read(SOURCE/'country_composition_coverage.csv')}
    temporal={}
    for r in legacy.read(SOURCE/'annual_composition_source_paths.csv'):temporal[r['country_id'],int(r['year'])]=r
    for c in packet['countries'].values():c['rows']=[];c['composition']=[]
    for r in rows:
        c=packet['countries'][r['country_id']];y=int(r['year']);s=temporal[r['country_id'],y]
        c['rows'].append(legacy.record(r,bounds[r['country_id'],y]))
        c['composition'].append(dict(year=y,updated=legacy.yes(r['dynamic_composition_used']),role=r['composition_update_role'],
            temporal=s['temporal_role'],grid_m=legacy.num(s.get('source_resolution_m')),
            nres_share=legacy.num(r['nonres_gfa_allocation_share'])))
    for c,v in packet['countries'].items():
        v['rows'].sort(key=lambda r:r[0]);v['composition'].sort(key=lambda r:r['year'])
        v['flags'].update(dynamic_history=legacy.yes(coverage[c]['improved_information_history']),
            dynamic_future=legacy.yes(coverage[c]['dynamic_projected_composition']),composition_fallback=coverage[c]['fallback_reason'])
    wb={(r['cohort_id'],int(r['year'])):r for r in legacy.read(OUT/'world_scenario_envelopes.csv')}
    packet['world']=sorted([legacy.record(r,wb['core194',int(r['year'])]) for r in legacy.read(OUT/'world_gfa_2015_2030.csv') if r['cohort_id']=='core194'],key=lambda r:r[0])
    packet.update(version=VERSION,snapshot='21 October 2026',sector_allocation='2020-preserving four-epoch GHSL relative sector-volume change',
        composition=dict(source='EC JRC GHS-BUILT-V R2023A',epochs=[2015,2020,2025,2030],
            historical_countries=191,projected_countries=189,new_fitted_parameters=0,
            allocation_is_GFA_truth=False,accuracy_upgrade_established=False,intermediate_years='interpolated',
            future_source_epochs='projected, not observed',fixed_height_epoch=2018),
        uncertainty_role='37 coherent sensitivity scenarios propagated through the adopted GHSL allocation; not confidence intervals',
        validation=legacy.read(SOURCE/'validation_paired_comparison.csv'))
    p.write_text('window.GFA_DATA='+json.dumps(packet,separators=(',',':'),ensure_ascii=False,allow_nan=False)+';\n')
    copies={OUT/'country_year_gfa_2015_2030.csv':'country-year-gfa.csv',OUT/'country_year_scenario_envelopes.csv':'country-scenario-ranges.csv',
        OUT/'world_gfa_2015_2030.csv':'world-gfa.csv',OUT/'world_scenario_envelopes.csv':'world-scenario-ranges.csv',
        SOURCE/'annual_composition_source_paths.csv':'annual-composition-sources.csv',SOURCE/'country_composition_coverage.csv':'composition-coverage.csv',
        SOURCE/'native_epoch_country_volumes.csv':'native-volume-epochs.csv',SOURCE/'validation_paired_comparison.csv':'validation-evidence.csv',
        SOURCE/'validation_country_metrics.csv':'validation-country-metrics.csv',SOURCE/'broad_native_interval_paired.csv':'nontraining-interval-comparison.csv',
        SOURCE/'validation_summary.json':'validation-summary.json',SOURCE/'model_protocol.json':'composition-protocol.json',
        SOURCE/'global_prediction_freeze.json':'composition-prediction-freeze.json',ROOT/'v7/dynamic_sector_composition.py':'composition-source.py',
        Path(__file__):'atlas-export-source.py',OUT/'release_checks.json':'release-checks.json'}
    for src,name in copies.items():shutil.copyfile(src,SITE/'downloads'/(PREFIX+name))
    manifest=dict(version=VERSION,snapshot=packet['snapshot'],countries=195,rows=3120,global_primary_countries=194,
        atlas_allocation_adopted=True,BIT_canonical_default_changed=False,model_refit=False,new_fitted_parameters=0,
        total_and2020preserved=True,sector_ranges_recomputed=True,scenario_count=37,scenario_ranges_are_CI=False,
        mixed_validation_preserved=True,scientific_accuracy_upgrade_claim=False,
        immutable_scientific_protocol=rec(SOURCE/'model_protocol.json'),adoption_protocol=rec(OUT/'adoption_protocol.json'),
        previous_site_archive=rec(SITE/'downloads/v16-atlas-before-ghsl-composition.zip'),
        inputs=[rec(src) for src in copies],exported_data=rec(p))
    save(SITE/'downloads'/(PREFIX+'manifest.json'),manifest)
    save(OUT/'export_manifest.json',manifest)
    print('adopted_dynamic_allocation_in_atlas',VERSION,flush=True)

if __name__=='__main__':
    release();export()
