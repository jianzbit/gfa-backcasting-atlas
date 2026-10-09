'use strict';
// This viewer reads frozen exports only. It has no fitting or parameter search.
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num = v => v === null || v === undefined || v === '' ? null : Number(v);
const fmt = (v, digits = 4) => num(v) === null ? '—' : Number(v).toLocaleString('en-US', {minimumFractionDigits:digits, maximumFractionDigits:digits});
const yes = v => v === true || String(v).toLowerCase() === 'true';
const colors = {v01:'#aeb6a5',v02:'#b89c7d',v03:'#83927c',v04:'#9f858c',v05:'#b49a69',v06:'#8a83a3',v07:'#c0806c',v08:'#759ab0',v09_compact:'#a494bb',v09_expanded:'#b68191',v10:'#728d94',v11:'#b18151',v12:'#547d69',v13:'#1e5845',native:'#1f3030'};
const short = id => id === 'native' ? 'Native reference' : id.replace('v09_compact','v0.9 C').replace('v09_expanded','v0.9 E').replace(/^v0([1-8])$/, 'v0.$1').replace(/^v(1[0-3])$/, 'v0.$1');
let data, selectedModels = new Set(['v03','v08','v12','v13']);

function table(headers, rows, cls='') {
  return `<table class="${esc(cls)}"><thead><tr>${headers.map(h=>`<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map((cell,i)=>i===0?`<th scope="row">${cell}</th>`:`<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}
function modelLabel(id) { return data.models.find(m=>m.id===id)?.version ? 'v'+data.models.find(m=>m.id===id).version : short(id); }
function friendly(value) { return String(value).replace('remove_group_A','Remove built-environment group').replace('remove_group_B','Remove construction group').replace('remove_group_C','Remove population group').replace('remove_group_D','Remove economic group').replace('remove_group_E','Remove stock/risk group').replace('remove_group_F','Remove lights group').replaceAll('_',' ').replace(/^./, c=>c.toUpperCase()); }

function bars(target, rows, options = {}) {
  const width = 900, left = options.left || 130, right = 74, top=23, gap=options.gap||32;
  const height = top+rows.length*gap+35;
  const values = rows.map(r=>Number(r.value));
  let min = options.signed ? Math.min(0,...values)*1.12 : 0;
  let max = Math.max(0,...values)*1.14;
  if(max===min) max=min+1;
  const x = v=>left+(v-min)/(max-min)*(width-left-right), zero=x(0);
  let body = '';
  for(let i=0;i<=4;i++){
    const value = min+(max-min)*i/4;
    body+=`<line x1="${x(value)}" x2="${x(value)}" y1="${top-12}" y2="${height-27}" stroke="#e6ebe2"/><text x="${x(value)}" y="${height-9}" fill="#7a897c" font-size="10" text-anchor="middle">${fmt(value,2)}</text>`;
  }
  rows.forEach((r,i)=>{
    const y=top+i*gap, end=x(r.value), color=r.color||colors[r.id]||'#64866d';
    body+=`<text x="${left-14}" y="${y+14}" fill="#536c5a" font-size="11" text-anchor="end">${esc(r.label||modelLabel(r.id))}</text>`;
    body+=`<rect class="bar chart-tooltip" tabindex="0" aria-label="${esc(r.label||modelLabel(r.id))}: ${fmt(r.value)}" x="${Math.min(end,zero)}" y="${y}" width="${Math.max(.8,Math.abs(end-zero))}" height="21" rx="2" fill="${color}"><title>${esc(r.label||modelLabel(r.id))}: ${fmt(r.value,6)} ${esc(options.unit||'log-error × 100')}</title></rect>`;
    body+=`<text x="${end+ (r.value<0?-9:9)}" y="${y+14}" fill="#385b45" font-size="11" text-anchor="${r.value<0?'end':'start'}">${fmt(r.value,4)}</text>`;
  });
  $(target).innerHTML=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(options.title||'Frozen model comparison')}"><title>${esc(options.title||'Frozen model comparison')}</title>${body}</svg>`;
}

function lines(target, series, options = {}) {
  const width=900,height=360,left=options.left||70,right=26,top=24,bottom=45;
  const finite=series.flatMap(s=>s.values.filter(v=>v!==null&&Number.isFinite(v)));
  if(!finite.length){$(target).innerHTML='<div class="empty-chart">No reliable historical estimates are available for this selection. Missing values have not been replaced.</div>';return;}
  let min=Math.min(...finite),max=Math.max(...finite),pad=Math.max((max-min)*.14,Math.abs(max)*.002,1e-9);
  min-=pad;max+=pad;
  const x=i=>left+i/5*(width-left-right),y=v=>height-bottom-(v-min)/(max-min)*(height-top-bottom);
  let out='';
  for(let i=0;i<=4;i++){
    const v=min+(max-min)*i/4;
    out+=`<line x1="${left}" x2="${width-right}" y1="${y(v)}" y2="${y(v)}" stroke="#e3e8df"/><text x="${left-12}" y="${y(v)+4}" font-size="10" fill="#728472" text-anchor="end">${fmt(v,options.digits??1)}</text>`;
  }
  for(let i=0;i<6;i++){
    out+=`<line x1="${x(i)}" x2="${x(i)}" y1="${top}" y2="${height-bottom}" stroke="#f1f3ee"/><text x="${x(i)}" y="${height-16}" fill="#728472" text-anchor="middle" font-size="11">${2015+i}</text>`;
  }
  series.forEach(s=>{
    let commands=[],prev=false;
    s.values.forEach((v,i)=>{if(v===null||!Number.isFinite(v)){prev=false;return;}commands.push(`${prev?'L':'M'}${x(i)},${y(v)}`);prev=true;});
    out+=`<path d="${commands.join(' ')}" fill="none" stroke="${s.color||colors[s.id]}" stroke-width="${s.id==='v13'||s.id==='native'?3:2}" ${s.id==='native'?'stroke-dasharray="5 4"':''} stroke-linecap="round"/>`;
    s.values.forEach((v,i)=>{if(v===null||!Number.isFinite(v))return;out+=`<circle class="chart-tooltip" tabindex="0" aria-label="${esc(s.label||modelLabel(s.id))}, ${2015+i}: ${fmt(v,options.tooltipDigits??4)}" cx="${x(i)}" cy="${y(v)}" r="${s.id==='v13'?4:3}" fill="${s.color||colors[s.id]}" stroke="white" stroke-width="1"><title>${esc(s.label||modelLabel(s.id))} · ${2015+i}: ${fmt(v,options.tooltipDigits??4)} ${esc(options.unit||'')}</title></circle>`;});
  });
  $(target).innerHTML=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(options.title||'Country historical trajectories')}"><title>${esc(options.title||'Country historical trajectories')}</title>${out}</svg>`;
}
function legend(target, series){$(target).innerHTML=series.map(s=>`<span><i style="background:${s.color||colors[s.id]}"></i>${esc(s.label||modelLabel(s.id))}</span>`).join('');}

function performance(){
  const metric=$('metric').value;
  const descriptions={macro_history_error_x100:'Country-macro mean absolute log error × 100 · 2015–2019',macro_interior_error_x100:'Country-macro mean absolute log error × 100 · 2016–2019',macro_endpoint_error_x100:'Country-macro absolute log error × 100 · 2015 endpoint',worst_country_error_x100:'Worst-country mean history log error × 100',excluding_KGZ_error_x100:'Macro history log error × 100 · remaining five scored countries'};
  $('metric-description').textContent=descriptions[metric];
  bars('performance-chart',data.scores.map(r=>({id:r.version,value:num(r[metric])})),{title:descriptions[metric]});
  $('score-table').innerHTML=table(['Model','History 2015–19','Intermediate 2016–19','2015 endpoint','Worst country','Better / worse vs v0.3','Excluding KGZ'],data.scores.map(r=>[esc(modelLabel(r.version)),fmt(r.macro_history_error_x100),fmt(r.macro_interior_error_x100),fmt(r.macro_endpoint_error_x100),fmt(r.worst_country_error_x100)+' · '+esc(r.worst_country),`${esc(r.improved_vs_v03)} / ${esc(r.worsened_vs_v03)}`,fmt(r.excluding_KGZ_error_x100)]));
}
function evidenceTables(){
  const countries=['CHL','DEU','DNK','KAZ','KGZ','ROU'];
  const max= Math.max(...data.country_scores.filter(r=>countries.includes(r.country_id)).map(r=>num(r.history_mean_abs_log_error_x100)));
  $('heatmap').innerHTML=table(['Version',...countries],data.scores.map(s=>[esc(modelLabel(s.version)),...countries.map(c=>{
    const row=data.country_scores.find(r=>r.country_id===c&&r.version===s.version),v=num(row.history_mean_abs_log_error_x100);
    return `<span style="display:block;background:rgba(81,127,91,${.07+.6*v/max});padding:5px 1px;border-radius:2px" title="${esc(c)} · ${esc(modelLabel(s.version))}: ${fmt(v,6)}">${fmt(v,2)}</span>`;
  })]),'heatmap-table');
  bars('external-chart',data.external.map(r=>({id:r.version,value:num(r.history_mean_abs_log_error_x100)})),{gap:30,title:'Korean partial external native-stock diagnostic, 2016–2019'});
  $('legacy-table').innerHTML=table(['Release','Original countries','History error ×100','Intermediate ×100','2015 endpoint ×100'],data.legacy.map(r=>[esc(modelLabel(r.version)),r.country_count===null?'Not evaluated':esc(r.country_count),fmt(r.history===null?null:r.history*100),fmt(r.interior===null?null:r.interior*100),fmt(r.endpoint===null?null:r.endpoint*100)]));
  $('shadow-table').innerHTML=table(['Release','History ×100','Intermediate ×100','2015 endpoint ×100','Worst ×100'],data.shadow.map(r=>[esc(modelLabel(r.version)),fmt(r.macro_history_error_x100),fmt(r.macro_interior_error_x100),fmt(r.macro_endpoint_error_x100),fmt(r.worst_country_error_x100)]));
  const labelRows=[...new Set(data.labels.map(r=>r.country_id))].map(c=>{const r=data.labels.find(x=>x.country_id===c);return[esc(c),esc(friendly(r.native_stock_scope||'Unresolved source scope')),esc(friendly(r.date_rule)),yes(r.temporal_training_eligible)?'Eligible weak reference':'Shadow / excluded','No'];});
  $('label-table').innerHTML=table(['Country','Native stock scope','Date rule','Training role','Aligned all-use GFA truth'],labelRows);
}

function initExplorer(){
  $('country').innerHTML=data.countries.map(c=>`<option value="${c.id}" ${c.id==='CHN'?'selected':''}>${esc(c.name)} · ${c.id}</option>`).join('');
  $('model-toggles').innerHTML=data.models.map(m=>`<label class="model-toggle"><input type="checkbox" value="${m.id}" ${selectedModels.has(m.id)?'checked':''}><i class="color-dot" style="background:${colors[m.id]}"></i>${esc(short(m.id))}</label>`).join('');
  $('model-toggles').addEventListener('change',e=>{if(e.target.matches('input')){e.target.checked?selectedModels.add(e.target.value):selectedModels.delete(e.target.value);countryChart();}});
  for(const id of ['country','units','path-source'])$(id).addEventListener('change',countryChart);
  $('select-all').addEventListener('click',()=>setSelected(data.models.map(m=>m.id)));
  $('select-latest').addEventListener('click',()=>setSelected(['v03','v08','v12','v13']));
  $('download-country').addEventListener('click',downloadCountry);
  countryChart();
}
function setSelected(ids){selectedModels=new Set(ids);document.querySelectorAll('#model-toggles input').forEach(el=>{el.checked=selectedModels.has(el.value);});countryChart();}
function countryChart(){
  const c=data.countries.find(c=>c.id===$('country').value),unit=$('units').value,source=$('path-source').value;
  const chosen=data.models.filter(m=>selectedModels.has(m.id)&&c[source][m.id]);
  const series=chosen.map(m=>({id:m.id,values:c[source][m.id].map((v,i,vs)=>v===null?null:unit==='absolute'?v/1e9:unit==='growth'?(i===0||vs[i-1]===null?null:(v/vs[i-1]-1)*100):(vs[5]===null?null:v/vs[5]*100))}));
  $('country-title').textContent=c.name;
  const label=unit==='absolute'?'GFA · billion m²':unit==='growth'?'Annual net change · %':'Index · 2020 = 100';
  $('country-subtitle').textContent=label+' · '+(source==='paths'?'Original release fits':'Matched-six comparator fits')+' · not validation';
  lines('country-chart',series,{title:c.name+' historical estimates, '+label,digits:unit==='absolute'?3:1,tooltipDigits:unit==='absolute'?6:4,unit:label});legend('country-legend',series);
  const gap=c.id==='PSE'?'No inherited 2020 anchor; no historical path.':c.id==='VAT'?'Only the inherited 2020 anchor is available; no historical path.':c.shared?'Shared-model path':'Inherited fallback path';
  const flag=c.support?.includes('extrapolation')?'Out-of-training-range feature flag · not validated AOA':'No out-of-range flag / see source support metadata';
  $('country-status').innerHTML=`<b>Latest release:</b> ${esc(gap)}<br><b>2020 anchor:</b> ${c.anchor===null?'Unavailable':fmt(c.anchor/1e9,6)+' billion m²'} · ${esc(flag)}<br><span>Inference uses covariates and shared rules. No target-country official GFA is required.</span>`;
  $('country-table').innerHTML='<p class="panel-note">Table stocks are in billion m², regardless of the selected chart axis. The last column is model-implied net stock change, not a validation error.</p>'+table(['Model',...data.years.map(String),'2015→2020 net change'],chosen.map(m=>{const v=c[source][m.id];return[esc(modelLabel(m.id)),...v.map(x=>fmt(x===null?null:x/1e9,6)),v[0]===null||v[5]===null?'—':fmt((v[5]/v[0]-1)*100,2)+'%'];}));
  const used=data.factors.filter(f=>c.factor_use[f.factor_name]?.[3]&&(c.factor_use[f.factor_name][0]||c.factor_use[f.factor_name][1]));
  $('country-factors').innerHTML=used.length?table(['Factor','Cumulative','Annual','Capacity','Quality'],used.map(f=>{const r=c.factor_use[f.factor_name];return[esc(f.display_name),r[0]?'Used':'—',r[1]?'Used':'—',r[2]?'Used':'—',esc(friendly(f.quality_class))];})):'<p class="panel-note">No v0.13 optional factors contribute to a complete shared path here. The source gap or inherited fallback remains explicit.</p>';
  document.querySelectorAll('#model-toggles input').forEach(el=>{el.disabled=source==='matched'&&!c.matched[el.value];el.closest('label').style.opacity=el.disabled?'.4':'1';});
}
function downloadCountry(){
  const c=data.countries.find(c=>c.id===$('country').value),source=$('path-source').value;
  const ids=data.models.filter(m=>selectedModels.has(m.id)&&c[source][m.id]).map(m=>m.id);
  const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
  const rows=[['country_id','country_name','year','unit','prediction_snapshot',...ids],...data.years.map((y,i)=>[c.id,c.name,y,'m2',source,...ids.map(id=>c[source][id][i])])];
  const blob=new Blob([rows.map(r=>r.map(quote).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=c.id+'-'+source+'-gfa.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function heldChart(){
  const country=$('held-country').value,ids=['v03','v08','v12','v13'];
  const rows=data.errors.filter(r=>r.country_id===country);
  const values=id=>data.years.map(y=>y===2020?100:(rows.find(r=>r.version===id&&Number(r.year)===y)?Math.exp(Number(rows.find(r=>r.version===id&&Number(r.year)===y).predicted_log_ratio_to_2020))*100:null));
  const series=ids.map(id=>({id,values:values(id)}));
  series.push({id:'native',label:'Native stock reference',values:data.years.map(y=>y===2020?100:(rows.find(r=>Number(r.year)===y)?Math.exp(Number(rows.find(r=>Number(r.year)===y).native_log_ratio_to_2020))*100:null))});
  lines('held-chart',series,{title:country+' excluded-country native-ratio comparison',unit:'2020 = 100'});legend('held-legend',series);
}

function modelDetails(id){
  const m=data.models.find(m=>m.id===id);document.querySelectorAll('#model-timeline button').forEach(b=>{b.classList.toggle('active',b.dataset.id===id);b.setAttribute('aria-pressed',String(b.dataset.id===id));});
  const params=m.parameters,tdf=params.total_effective_degrees_of_freedom,adf=params.timing_effective_degrees_of_freedom;
  const active=Object.entries(m.factors);
  $('model-detail').innerHTML=`<div class="model-detail-main"><div class="eyebrow">${esc(m.phase.toUpperCase())} / v${esc(m.version)}</div><h3>${esc(m.title)}</h3><div class="model-meta">${esc(m.date)} · ${esc(m.status)} · ${m.complete_paths} complete country paths</div><p>${esc(m.description)}</p><div class="equation">${esc(m.equation)}</div><h4>How it is fitted</h4><p>${esc(m.fitting)}</p><h4>Evidence scope</h4><p>${m.matched_comparison?'A matched six-country refit is available in the main comparison. The original archived release fit is preserved separately.':'No matched-six result is available. Inspect the original archived diagnostic separately; no score is inferred from a full-fit path.'} All shared fits use weak native stock references; none establishes globally aligned all-use GFA accuracy.</p><a href="${esc(m.code_url)}" target="_blank" rel="noopener">Read model implementation · team access ↗</a><br><a href="${esc(m.source_url)}" target="_blank" rel="noopener">Read the frozen release archive · team access ↗</a></div><div class="model-detail-side"><h4>Actual predictor roles</h4><div class="factor-chips">${active.map(([f,r])=>`<span title="${esc(f)}">${esc(data.factors.find(x=>x.factor_name===f)?.display_name||f.replaceAll('_',' '))}<br><small>${esc(r.join(' + '))}</small></span>`).join('')}</div><div class="model-params"><div><strong>${m.training.length||'—'}</strong><span>countries in original release fit</span></div><div><strong>${active.length}</strong><span>qualified predictors / prior entries</span></div>${tdf!==undefined?`<div><strong>${fmt(tdf,2)}</strong><span>cumulative effective degrees of freedom</span></div><div><strong>${fmt(adf,2)}</strong><span>annual effective degrees of freedom</span></div>`:''}</div><details><summary>Frozen parameters and physical mechanism groups</summary><pre>${esc(JSON.stringify(params,null,2))}</pre></details><p class="panel-note">No country-specific fitted parameters. Missing sources retain explicit gaps or shared fallback rules. Gross construction and demolition are not separately identified.</p></div>`;
}
function initModels(){
  $('model-timeline').innerHTML=data.models.map(m=>`<button type="button" data-id="${m.id}" aria-pressed="false">v${esc(m.version)}</button>`).join('');
  $('model-timeline').addEventListener('click',e=>{const b=e.target.closest('button');if(b)modelDetails(b.dataset.id);});modelDetails('v13');
  const precursors=[['Reference & input audit','2026-10-05-reference-audit'],['Hierarchical prototype','2026-10-06-hierarchical-backcast'],['Relative trends & fixed 0.50','2026-10-06-relative-trends'],['Country transfer','2026-10-07-country-transfer'],['Country transfer · second wave','2026-10-07-country-transfer-wave2'],['Input & assumption audit','2026-10-07-input-assumption-audit'],['Spatial model comparison','2026-10-07-spatial-model-comparison'],['Factor development audit','2026-10-08-v09-development-audit']];
  $('precursor-links').innerHTML=precursors.map(([name,folder])=>`<a href="${esc(data.source_repository)}/tree/${data.source_commit}/review/${folder}" target="_blank" rel="noopener">${esc(name)} ↗</a>`).join('');
}

function activeFactor(f){return f.models.v13?.some(r=>r!=='horizontal prior');}
function factors(){
  const query=$('factor-search').value.toLowerCase(),group=$('factor-group').value,filter=$('factor-usage').value;
  const fs=data.factors.filter(f=>(group==='all'||f.group===group)&&(!query||[f.display_name,f.factor_name,f.source].join(' ').toLowerCase().includes(query))&&(filter==='all'||(filter==='active'?activeFactor(f):!activeFactor(f))));
  $('factor-count').textContent=`${fs.length} of 43 candidates · ${data.factors.filter(activeFactor).length} active qualified v0.13 predictors plus the frozen horizontal prior`;
  $('factor-table').innerHTML=table(['Factor / details','Source','Group','Qualified source support','v0.13 role','Countries used: cumulative / annual'],fs.map(f=>{
    const count=num(f.coverage.complete_five_qualified_countries??f.complete_five_qualified_feature_countries)||0;
    const roles=f.models.v13||[];
    const support=f.static_context?`${f.qualified_any_countries} context countries`:`${count} complete / ${Math.max(0,f.qualified_any_countries-count)} partial`;
    return[`<button class="factor-button" type="button" data-factor="${esc(f.factor_name)}">${esc(f.display_name)}</button>`,esc(f.source),esc(f.group),`${support}<div class="coverage-bar"><i style="width:${f.qualified_any_countries/195*100}%"></i></div>`,roles.length?roles.map(r=>`<span class="role-tag">${esc(r)}</span>`).join(''):'<span class="role-tag inactive">Inactive</span>',`${f.used_total_countries} / ${f.used_annual_countries}`];
  }));
}
function factorModal(name){
  const f=data.factors.find(f=>f.factor_name===name);if(!f)return;
  const fields=[['Factor ID',f.factor_name],['Mechanism','Group '+f.group],['Source',f.source],['Original unit',f.original_unit],['Transformation',f.transformation],['Quality',friendly(f.quality_class)],['Source role',f.source_role],['GFA relevance',f.applicability_to_GFA_prediction],['Limitations',f.source_limits],['Any original data',f.countries_with_any_original+' countries'],['Full source years',f.complete_six_original_countries+' countries'],['v0.13 role',(f.models.v13||['Inactive']).join(' + ')]];
  $('factor-detail').innerHTML=`<div class="eyebrow">FACTOR LIBRARY / ${esc(f.group)}</div><h3>${esc(f.display_name)}</h3><dl>${fields.map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}<dt>Source link</dt><dd><a href="${esc(f.source_url)}" target="_blank" rel="noopener">Read source documentation ↗</a></dd></dl>`;
  $('factor-dialog').showModal();
}
function initFactors(){
  ['factor-search','factor-group','factor-usage'].forEach(id=>$(id).addEventListener(id==='factor-search'?'input':'change',factors));
  $('factor-table').addEventListener('click',e=>{const b=e.target.closest('[data-factor]');if(b)factorModal(b.dataset.factor);});
  $('close-factor').addEventListener('click',()=>$('factor-dialog').close());
  $('factor-dialog').addEventListener('click',e=>{if(e.target===$('factor-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
  $('factor-matrix').innerHTML=table(['Factor',...data.models.map(m=>short(m.id))],data.factors.map(f=>[esc(f.display_name),...data.models.map(m=>{const r=f.models[m.id];return r?`<span title="${esc(r.join(' + '))}">${r.includes('horizontal prior')?'Prior':r.map(x=>({cumulative:'C',annual:'A',capacity:'K','proxy observation':'O','shared predictor':'●'}[x]||'●')).join('/')}</span>`:'—';})]));
  $('factor-matrix').insertAdjacentHTML('beforeend','<p class="panel-note">C = cumulative · A = annual · K = capacity · O = separate proxy observation · ● = shared predictor · Prior = preserved horizontal baseline</p>');factors();
}

function ablations(){
  const v=$('ablation-version').value,full=num(data.scores.find(r=>r.version===v).macro_history_error_x100);
  const rows=data.ablations[v];
  bars('ablation-chart',rows.map(r=>({id:r.ablation,label:friendly(r.ablation),value:num(r.macro_history_error_x100)-full,color:num(r.macro_history_error_x100)<full?'#728d6d':'#ba8b64'})),{signed:true,left:280,gap:31,title:`${modelLabel(v)} refitted ablation minus full history error`,unit:'change in log-error ×100'});
  $('ablation-table').innerHTML=table(['Ablation/control','History ×100','Difference vs full','Intermediate ×100','2015 endpoint ×100'],rows.map(r=>[esc(friendly(r.ablation)),fmt(r.macro_history_error_x100),fmt(num(r.macro_history_error_x100)-full),fmt(r.macro_interior_error_x100),fmt(r.macro_endpoint_error_x100)]));
}

async function start(){
  try{
    const response=await fetch('data/research.json');if(!response.ok)throw new Error(`Research data unavailable (${response.status})`);data=await response.json();
    performance();evidenceTables();initExplorer();initModels();initFactors();heldChart();ablations();
    $('metric').addEventListener('change',performance);$('held-country').addEventListener('change',heldChart);$('ablation-version').addEventListener('change',ablations);
    $('load-status').hidden=true;
  }catch(error){$('load-status').textContent='Unable to load the research charts. Downloadable tables remain available.';console.error(error);}
}
start();
