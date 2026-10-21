(function(root){
  'use strict';
  const SECTORS={total:{column:1,low:4,label:'Total'},residential:{column:2,low:6,label:'Residential'},non_residential:{column:3,low:8,label:'Non-residential'}};
  const CHART_PHASES=[
    {id:'backcast',label:'BACKCAST',start:2015,end:2020,line:'#827551',background:'#f1eee4',dash:''},
    {id:'nowcast',label:'NOWCAST',start:2020,end:2026,line:'#27806b',background:'#e6f0e9',dash:'8 5'},
    {id:'forecast',label:'FORECAST',start:2026,end:2030,line:'#4c7393',background:'#e5ebf2',dash:'5 5'}
  ];
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const finite=v=>typeof v==='number'&&Number.isFinite(v);
  function phase(y){return y<2020?'Historical backcast':y===2020?'Fixed proxy anchor':y<=2025?'Modeled reconstruction':y===2026?'Model-based nowcast':'Conditional forecast';}
  function normalizeSelection(s,data){
    let start=Number(s.start),end=Number(s.end);
    if(!Number.isInteger(start)||start<2015||start>2029)start=2015;
    if(!Number.isInteger(end)||end<2016||end>2030)end=2030;
    if(start>=end)end=Math.min(2030,start+1);
    return {country:s.country==='WORLD'||data.countries[s.country]?s.country:'WORLD',sector:SECTORS[s.sector]?s.sector:'total',start,end,
      view:['level','net','rate','index'].includes(s.view)?s.view:'level',unit:['auto','million','billion'].includes(s.unit)?s.unit:'auto',range:s.range!==false};
  }
  function moveEndpoint(s,endpoint,year){
    if(!['start','end'].includes(endpoint)||!finite(year))return {...s};
    const min=endpoint==='start'?2015:s.start+1,max=endpoint==='start'?s.end-1:2030;
    return {...s,[endpoint]:Math.min(max,Math.max(min,Math.round(year)))};
  }
  function yearAtPlotX(position,left,width){
    if(!finite(position)||!finite(left)||!finite(width)||width<=0)return null;
    return Math.min(2030,Math.max(2015,Math.round(2015+15*(position-left)/width)));
  }
  function series(data,country){return country==='WORLD'?data.world:data.countries[country].rows;}
  function statistics(rows,sector,start,end){
    const k=SECTORS[sector].column,a=rows.find(r=>r[0]===start),b=rows.find(r=>r[0]===end);
    if(!a||!b||!finite(a[k])||!finite(b[k])||a[k]<=0||end<=start)return {start:null,end:null,delta:null,growth:null,cagr:null,years:end-start};
    return {start:a[k],end:b[k],delta:b[k]-a[k],growth:100*(b[k]/a[k]-1),cagr:100*(Math.pow(b[k]/a[k],1/(end-start))-1),years:end-start};
  }
  function chartValues(rows,sector,view){
    const {column:k,low}=SECTORS[sector],base=rows.find(r=>r[0]===2020)?.[k];
    return rows.map((r,i)=>{
      const prev=rows[i-1],v=r[k];let value=v,lo=r[low],hi=r[low+1];
      if(view==='net')value=prev&&r[0]-prev[0]===1?v-prev[k]:null;
      if(view==='rate')value=prev&&r[0]-prev[0]===1&&prev[k]>0?100*(v/prev[k]-1):null;
      if(view==='index'){value=base>0?100*v/base:null;lo=hi=null;}
      if(view==='net'||view==='rate')lo=hi=null;
      return {year:r[0],value,lo,hi,stock:v};
    });
  }
  function units(rows,sector,requested){
    const maximum=Math.max(...rows.map(r=>r[SECTORS[sector].column]));
    const use=requested==='auto'?(maximum>=1e9?'billion':'million'):requested;
    return {key:use,scale:use==='billion'?1e9:1e6,label:use==='billion'?'billion m²':'million m²',short:use==='billion'?'bn m²':'mn m²'};
  }
  function number(v,d=2){return finite(v)?new Intl.NumberFormat('en-US',{minimumFractionDigits:0,maximumFractionDigits:d}).format(v):'Unavailable';}
  function signed(v,d=2){return finite(v)?(v>0?'+':'')+number(v,d):'Unavailable';}
  function area(v,u,sign=false){if(!finite(v))return 'Unavailable';const a=v/u.scale,precision=Math.abs(a)>0&&Math.abs(a)<.001?8:Math.abs(a)<.1?4:Math.abs(a)<10?3:2;return (sign&&v>0?'+':'')+number(a,precision);}
  function compositionBasis(data,country,year){
    if(year===2020)return 'Preserved 2020 sector anchors';
    if(country==='WORLD')return 'Country-specific GHSL allocation / retained fallbacks';
    const row=data.countries[country]?.composition?.find(r=>r.year===year);
    if(!row)return 'Retained v16 sector path';
    if(!row.updated)return row.role.includes('zero_source')?'Retained v16 · zero source reference':'Retained v16 · no qualified epoch bundle';
    if(year===2015)return 'GHSL modeled epoch · '+row.grid_m+' m';
    if(year<2020)return 'GHSL historical interpolation';
    if(year===2025||year===2030)return 'GHSL projected epoch · '+row.grid_m+' m';
    return 'Interpolation involving GHSL projections';
  }
  function makeCSV(rows,country,name,core,start,end,metadata={}){
    const header=['country_id','country_name','year','total_gfa_m2','residential_gfa_m2','non_residential_gfa_m2','total_scenario_min_m2','total_scenario_max_m2','residential_scenario_min_m2','residential_scenario_max_m2','non_residential_scenario_min_m2','non_residential_scenario_max_m2','total_annual_net_change_m2','total_annual_growth_percent','estimate_role','core194_included','selected_interval','uncertainty_role','model_version','sector_split_basis'];
    const cell=v=>'"'+String(v??'').replace(/"/g,'""')+'"';
    return [header,...rows.map((r,i)=>[country,name,...r, i?r[1]-rows[i-1][1]:'',i?100*(r[1]/rows[i-1][1]-1):'',country==='PSE'&&r[0]>=2023?'counterfactual_unadjusted_stock_baseline':phase(r[0]),core,r[0]>=start&&r[0]<=end,metadata.uncertainty_role||'37 structural sensitivity scenarios; not calibrated confidence intervals',metadata.version||'v16',metadata.countries?compositionBasis(metadata,country,r[0]):'Retained v16 sector path'])].map(r=>r.map(cell).join(',')).join('\r\n');
  }
  function tickStep(maximum){const raw=maximum/4,p=10**Math.floor(Math.log10(raw||1));return [1,2,2.5,5,10].map(v=>v*p).find(v=>v>=raw)||10*p;}
  function buildSVG(rows,s,u,width=1060,name='Country'){
    const w=Math.max(300,Math.round(width)),mobile=w<600,h=mobile?332:430,p={l:mobile?45:62,r:mobile?15:24,t:62,b:45},pw=w-p.l-p.r,ph=h-p.t-p.b;
    const vals=chartValues(rows,s.sector,s.view),isArea=s.view==='level'||s.view==='net',scale=isArea?u.scale:1;
    let nums=vals.map(v=>v.value).filter(finite);
    if(s.range&&s.view==='level')nums.push(...vals.flatMap(v=>[v.lo,v.hi]).filter(finite));
    const low=Math.min(0,...nums.map(v=>v/scale)),high=Math.max(0,...nums.map(v=>v/scale)),step=tickStep(high-low||1);
    let bottom=Math.floor(low/step)*step,top=Math.ceil(high/step)*step;if(top===bottom)top=bottom+1;
    const x=y=>p.l+(y-2015)/15*pw,y=v=>p.t+(top-v/scale)/(top-bottom)*ph,path=a=>a.map((v,i)=>(i?'L':'M')+x(v.year).toFixed(2)+','+y(v.value).toFixed(2)).join(' ');
    const labels=mobile?[2015,2020,2026,2030]:[2015,2018,2020,2023,2026,2030];
    const font=mobile?10:11,clip='plot-clip';
    const parts=[`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="group" aria-labelledby="chart-svg-title chart-svg-desc"><title id="chart-svg-title">${esc(name)}: ${esc(SECTORS[s.sector].label)} ${esc(s.view)} estimates, 2015–2030</title><desc id="chart-svg-desc">Selected interval ${s.start} to ${s.end}. Drag the FROM and TO circles, or use their arrow keys, to change comparison years. Three connected display regions: Backcast 2015–2020, Nowcast 2020–2026 including modeled reconstruction, and Forecast 2026–2030. The 2020 anchor and 2026 estimate are shared connection points. All values are model estimates; the sensitivity envelope is not a confidence interval.</desc><style>text{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:${font}px;fill:#6b736a}.point{cursor:crosshair}.point:focus{outline:none;stroke:#2e6c58;stroke-width:4}.comparison-handle{cursor:ew-resize;touch-action:none;outline:none}.comparison-handle circle{touch-action:none}.comparison-handle:focus-visible .handle-ring{stroke-width:4}.comparison-handle:focus-visible .handle-halo{opacity:.22}</style><defs><clipPath id="${clip}"><rect x="${p.l}" y="${p.t}" width="${pw}" height="${ph}"/></clipPath></defs>`];
    CHART_PHASES.forEach(stage=>{
      const xx=x(stage.start),ww=x(stage.end)-xx,mid=xx+ww/2;
      parts.push(`<rect data-region="${stage.id}" x="${xx}" y="${p.t-42}" width="${ww}" height="${ph+42}" fill="${stage.background}"/><text x="${mid}" y="${p.t-24}" text-anchor="middle" style="fill:${stage.line};font-size:${mobile?8:11}px;font-weight:700;letter-spacing:${mobile ? 0.4 : 1}px">${stage.label}</text><text x="${mid}" y="${p.t-10}" text-anchor="middle" style="font-size:${mobile?8:10}px">${stage.start}–${stage.end}</text>`);
    });
    parts.push(`<rect data-selection-range="true" x="${x(s.start)}" y="${p.t}" width="${x(s.end)-x(s.start)}" height="${ph}" fill="#829c88" opacity=".075"/>`);
    const ticks=Math.round((top-bottom)/step);
    for(let j=0;j<=ticks;j++){const value=bottom+j*step,yy=y(value*scale),precision=Math.abs(step)<1?Math.min(8,Math.ceil(-Math.log10(Math.abs(step)))+1):1;parts.push(`<line x1="${p.l}" x2="${w-p.r}" y1="${yy}" y2="${yy}" stroke="#d9dad0" stroke-width="1"/><text x="${p.l-10}" y="${yy+4}" text-anchor="end">${number(value,precision)}${s.view==='rate'?'%':''}</text>`);}
    labels.forEach(year=>parts.push(`<text x="${x(year)}" y="${h-15}" text-anchor="${year===2015?'start':year===2030?'end':'middle'}">${year}</text>`));
    [2020,2026].forEach(year=>parts.push(`<line data-boundary="${year}" x1="${x(year)}" x2="${x(year)}" y1="${p.t-42}" y2="${h-p.b}" stroke="#a8b1aa" stroke-width="1" stroke-dasharray="3 5"/>`));
    if(s.view==='level'&&s.range){const lower=vals.filter(v=>finite(v.lo)&&finite(v.hi)),pp=lower.map((v,i)=>(i?'L':'M')+x(v.year)+','+y(v.hi)).join(' ')+lower.slice().reverse().map(v=>'L'+x(v.year)+','+y(v.lo)).join(' ')+'Z';parts.push(`<path d="${pp}" fill="#b9b29a" opacity=".24" clip-path="url(#${clip})"/>`);}
    if(s.view==='net'||s.view==='rate'){
      vals.filter(v=>finite(v.value)).forEach(v=>{const yy=y(v.value),zero=y(0),bw=Math.max(5,pw/15*.42),selected=v.year>=s.start&&v.year<=s.end,stage=CHART_PHASES.find(p=>v.year<=p.end);parts.push(`<rect x="${x(v.year)-bw/2}" y="${Math.min(yy,zero)}" width="${bw}" height="${Math.max(1,Math.abs(yy-zero))}" fill="${v.value<0?'#ad7b60':stage.line}" opacity="${selected?'.85':'.3'}"/>`);});
    }else{
      CHART_PHASES.forEach(stage=>{const vv=vals.filter(v=>v.year>=stage.start&&v.year<=stage.end&&finite(v.value));parts.push(`<path data-phase="${stage.id}" data-start-year="${stage.start}" data-end-year="${stage.end}" d="${path(vv)}" fill="none" stroke="${stage.line}" stroke-width="${mobile?2.5:3.1}" ${stage.dash?`stroke-dasharray="${stage.dash}"`:''}/>`);});
    }
    vals.filter(v=>finite(v.value)).forEach(v=>{
      const xx=x(v.year),yy=y(v.value),inRange=v.year>=s.start&&v.year<=s.end,r=mobile?3.2:4.1,stage=CHART_PHASES.find(p=>v.year<=p.end),fill=v.year===2026?'#27806b':'#f8f7f1',desc=`${v.year}: ${number(v.value/scale,4)} ${isArea?u.label:s.view==='rate'?'percent':'index points'}, ${phase(v.year)}`;
      if(v.year===2020)parts.push(`<rect x="${xx-r}" y="${yy-r}" width="${r*2}" height="${r*2}" fill="#f8f7f1" stroke="#827551" stroke-width="2" transform="rotate(45 ${xx} ${yy})"/>`);
      else parts.push(`<circle cx="${xx}" cy="${yy}" r="${v.year===s.end||v.year===2026?r+1.5:r}" fill="${fill}" stroke="${stage.line}" stroke-width="2" opacity="${inRange?1:.45}"/>`);
      parts.push(`<circle class="point" data-year="${v.year}" tabindex="0" role="img" aria-label="${esc(desc)}" cx="${xx}" cy="${yy}" r="${mobile?9:10}" fill="transparent" stroke="transparent"><title>${esc(desc)}</title></circle>`);
    });
    const end=vals.find(v=>v.year===s.end);if(end&&finite(end.value)&&x(s.end)-x(s.start)>74){const xx=x(end.year),yy=Math.max(p.t+13,y(end.value)-15),a=Math.abs(end.value/scale),precision=a>0&&a<.001?8:a<.1?4:a<1?3:1,stage=CHART_PHASES.find(p=>end.year<=p.end);parts.push(`<text x="${xx-3}" y="${yy}" text-anchor="end" style="fill:${stage.line};font-size:${mobile?13:17}px;font-weight:600">${number(end.value/scale,precision)}${s.view==='rate'?'%':''}</text>`);}
    const endpointY=endpoint=>{const v=vals.find(v=>v.year===s[endpoint]);return y(v&&finite(v.value)?v.value:0);};
    const separateHandles=x(s.end)-x(s.start)<48&&Math.abs(endpointY('end')-endpointY('start'))<48;
    const separatedTop=Math.max(p.t+22,Math.min(h-p.b-74,(endpointY('start')+endpointY('end'))/2-26));
    ['start','end'].forEach(endpoint=>{
      const year=s[endpoint],xx=x(year),stockY=endpointY(endpoint),yy=separateHandles?separatedTop+(endpoint==='start'?0:52):stockY,color=endpoint==='start'?'#625538':'#2e6c58',label=endpoint==='start'?'FROM':'TO';
      const tagWidth=mobile?65:74,tagX=Math.max(p.l+tagWidth/2,Math.min(w-p.r-tagWidth/2,xx)),tagY=Math.max(p.t+14,Math.min(h-p.b-14,yy+(endpoint==='start'?-32:32)));
      const min=endpoint==='start'?2015:s.start+1,max=endpoint==='start'?s.end-1:2030;
      if(separateHandles)parts.push(`<line x1="${xx}" x2="${xx}" y1="${stockY}" y2="${yy}" stroke="${color}" stroke-width="1.5" pointer-events="none"/>`);
      parts.push(`<line x1="${xx}" x2="${xx}" y1="${p.t}" y2="${h-p.b}" stroke="${color}" opacity=".4" stroke-dasharray="3 4" pointer-events="none"/><g pointer-events="none"><rect x="${tagX-tagWidth/2}" y="${tagY-10}" width="${tagWidth}" height="20" rx="4" fill="#fffefb" stroke="${color}" stroke-opacity=".3"/><text x="${tagX}" y="${tagY+3}" text-anchor="middle" style="fill:${color};font-size:${mobile?9:10}px;font-weight:700">${label} ${year}</text></g><g class="comparison-handle" data-handle="${endpoint}" role="slider" tabindex="0" aria-label="Comparison ${endpoint} year" aria-orientation="horizontal" aria-valuemin="${min}" aria-valuemax="${max}" aria-valuenow="${year}" aria-valuetext="${label} ${year}. Drag or use arrow keys to change year."><title>${label} ${year}: drag horizontally or use arrow keys</title><circle class="handle-halo" cx="${xx}" cy="${yy}" r="16" fill="${color}" opacity=".12"/><circle class="handle-ring" cx="${xx}" cy="${yy}" r="9" fill="#fffefb" stroke="${color}" stroke-width="2.5"/><circle cx="${xx}" cy="${yy}" r="3" fill="${color}"/><circle class="handle-hit" cx="${xx}" cy="${yy}" r="24" fill="transparent"/></g>`);
    });
    parts.push('</svg>');return parts.join('');
  }
  function factorRows(data,state,search='',group='all',status='all'){
    return data.factors.map(f=>{
      let use=state.country==='WORLD'?[f.period_countries>0,f.timing_countries>0,0,f.static,null]:data.countries[state.country].factors[f.id]||[false,false,0,false,null];
      const indirect=f.role==='part_of_single_construction_distributed_lag';
      if(indirect){const parent='annual_log_real_construction_value_added_change',p=data.factors.find(v=>v.id===parent);use=state.country==='WORLD'?[p.period_countries>0,p.timing_countries>0,0,false,null]:data.countries[state.country].factors[parent]||[false,false,0,false,null];}
      const prior=f.role==='horizontal_prior_not_fitted_feature',isPrior=prior&&(state.country==='WORLD'||data.countries[state.country].flags.horizontal==='legacy_GHSL_endpoint_mean');
      const used=use[0]||use[1]||isPrior;
      return {f,use,isPrior,used,indirect};
    }).filter(({f,use,used})=>(group==='all'||f.group===group)&&(!search||[f.label,f.id,f.source,f.group_label].join(' ').toLowerCase().includes(search.toLowerCase()))&&(status==='all'||status==='used'&&used||status==='unused'&&!used||status==='annual'&&use[1]||status==='static'&&use[3]));
  }
  const api={SECTORS,phase,normalizeSelection,moveEndpoint,yearAtPlotX,series,statistics,chartValues,units,makeCSV,compositionBasis,buildSVG,factorRows};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  root.GFAExplorer=api;
  if(!root.document||!root.GFA_DATA)return;
  const D=root.GFA_DATA,$=id=>root.document.getElementById(id),short={USA:'United States',GBR:'United Kingdom',KOR:'South Korea',PRK:'North Korea',RUS:'Russia',VNM:'Vietnam',LAO:'Laos',TZA:'Tanzania',BOL:'Bolivia',VEN:'Venezuela',IRN:'Iran',SYR:'Syria',PSE:'State of Palestine',COD:'Democratic Republic of the Congo',COG:'Republic of the Congo',MDA:'Moldova'};
  const name=c=>c==='WORLD'?'Global · core 194 countries':short[c]||D.countries[c].name;
  const hash=new URLSearchParams(root.location.search);
  let state=normalizeSelection({country:hash.get('country')||'WORLD',sector:hash.get('sector'),start:hash.get('from'),end:hash.get('to'),view:hash.get('view'),unit:hash.get('unit'),range:hash.get('range')!=='off'},D),toastTimer;
  function toast(msg){$('toast').textContent=msg;$('toast').hidden=false;root.clearTimeout(toastTimer);toastTimer=root.setTimeout(()=>$('toast').hidden=true,3500);}
  function saveURL(){const p=new URLSearchParams({country:state.country,sector:state.sector,from:state.start,to:state.end,view:state.view,unit:state.unit,range:state.range?'on':'off'});root.history.replaceState(null,'',root.location.pathname+'?'+p.toString()+root.location.hash);}
  function download(body,filename,type){const blob=new Blob([body],{type}),url=URL.createObjectURL(blob),a=root.document.createElement('a');a.href=url;a.download=filename;a.click();root.setTimeout(()=>URL.revokeObjectURL(url),2000);}
  function renderChart(){
    const focusedHandle=$('chart').contains(root.document.activeElement)?root.document.activeElement.dataset.handle:null;
    const r=series(D,state.country),u=units(r,state.sector,state.unit),labels={level:'Estimated floorspace',net:'Annual net area change',rate:'Annual growth rate',index:'Floorspace index'};
    $('chart-title').textContent=SECTORS[state.sector].label+' · '+labels[state.view].toLowerCase();
    $('chart-subtitle').textContent='Nominal year-end estimates · '+(state.view==='rate'?'percent':state.view==='index'?'2020 = 100':u.label);
    $('chart').innerHTML=buildSVG(r,state,u,$('chart').clientWidth||1060,name(state.country));
    $('show-range').disabled=state.view!=='level';$('unit').disabled=state.view==='rate'||state.view==='index';
    $('range-note').textContent=state.view==='level'?'The shaded envelope spans 37 coherent sensitivity scenarios, each propagated through the adopted GHSL sector allocation. It conditions on the selected GHSL paths; it is not a calibrated confidence interval.':state.view==='index'?'The 2020 index is fixed at 100 by normalization. Relative changes do not validate the absolute 2020 anchor.':'Annual changes compare adjacent nominal year-end stocks. The first year has no preceding-year estimate and remains unavailable. No growth confidence interval is implied.';
    $('chart').querySelectorAll('[data-year]').forEach(el=>{const show=()=>readout(Number(el.dataset.year));el.addEventListener('mouseenter',show);el.addEventListener('focus',show);el.addEventListener('click',show);});
    if(focusedHandle)$('chart').querySelector(`[data-handle="${focusedHandle}"]`)?.focus({preventScroll:true});
    readout(state.end);
  }
  function readout(year){
    const r=series(D,state.country),row=r.find(v=>v[0]===year),k=SECTORS[state.sector].column,u=units(r,state.sector,state.unit),prev=r.find(v=>v[0]===year-1),growth=prev?100*(row[k]/prev[k]-1):null;
    $('chart-readout').innerHTML=`<strong>${year}</strong> &nbsp; ${area(row[k],u)} ${u.label} &nbsp; · &nbsp; ${esc(phase(year))}${finite(growth)?' &nbsp; · &nbsp; '+signed(growth)+'% year on year':''}${state.sector!=='total'?' · '+esc(compositionBasis(D,state.country,year)):''}${state.country==='PSE'&&year>=2023?' · Counterfactual baseline; conflict losses not measured':''}`;
  }
  function renderMetrics(){
    const r=series(D,state.country),u=units(r,state.sector,state.unit),m=statistics(r,state.sector,state.start,state.end);
    $('explorer-heading').textContent=state.country==='WORLD'?"The world's building floorspace.":name(state.country)+' · building floorspace';
    $('level-label').textContent=`${SECTORS[state.sector].label} GFA in ${state.end}`;
    $('level-value').innerHTML=area(m.end,u)+`<span class="value-unit">${u.short}</span>`;
    $('level-note').textContent=phase(state.end);
    $('change-label').textContent=`Net area change · ${state.start}–${state.end}`;
    $('change-value').innerHTML=area(m.delta,u,true)+`<span class="value-unit">${u.short}</span>`;
    $('change-note').textContent=`From ${area(m.start,u)} to ${area(m.end,u)} ${u.label}`;
    $('growth-value').textContent=signed(m.growth)+'%';$('growth-note').textContent=`Total change over ${m.years} years`;
    $('cagr-value').textContent=signed(m.cagr)+'%';$('cagr-note').textContent='Equivalent compounded annual rate';
    const note=$('country-note');note.className='country-note';
    if(state.country==='WORLD')note.textContent='Balanced sum of 194 countries at every date. The Palestine supplement is excluded from this primary aggregate.';
    else if(state.country==='PSE'){note.className+=' warning';note.textContent='Source-conditioned supplement. The 2020 level uses a shared peer conversion. From 2023 onward this is a counterfactual unadjusted stock baseline: conflict destruction and reconstruction are not measured. It is excluded from the primary global total.';}
    else{const d=D.countries[state.country].flags;note.textContent=(d.extrapolation?'Predictor-range extrapolation flagged. ':'')+'2020 composition: '+(d.donors?'shared peer-median allocation ('+d.donors+' donors).':'conditional source-volume allocation.')+' Research estimate; no calibrated country accuracy score.';}
    if(D.composition){
      if(state.country==='WORLD')note.textContent+=' Dynamic GHSL sector allocation covers '+D.composition.historical_countries+' historical and '+D.composition.projected_countries+' future paths in the 195-country roster.';
      else{const d=D.countries[state.country].flags;note.textContent+=' Sector split: '+(d.dynamic_history?'GHSL 2015–2020 path':'retained v16 history')+'; '+(d.dynamic_future?'GHSL projected 2020/2025/2030 path':'retained v16 future path')+'.';}
    }
  }
  function renderAnnual(){
    const r=series(D,state.country),u=units(r,state.sector,state.unit),k=SECTORS[state.sector].column;
    $('annual-table').innerHTML=`<table><thead><tr><th>Year</th><th>Total (${u.short})</th><th>Residential</th><th>Non-residential</th><th>Selected-use net change</th><th>Selected-use growth</th><th>Estimate role</th><th>Sector split basis</th></tr></thead><tbody>`+r.map((v,i)=>{const prev=r[i-1],delta=prev?v[k]-prev[k]:null,growth=prev?100*(v[k]/prev[k]-1):null;return `<tr class="${v[0]===state.start||v[0]===state.end?'selected-year':''}"><td>${v[0]}</td><td class="num">${area(v[1],u)}</td><td class="num">${area(v[2],u)}</td><td class="num">${area(v[3],u)}</td><td class="num">${area(delta,u,true)}</td><td class="num">${finite(growth)?signed(growth)+'%':'Unavailable'}</td><td class="phase">${esc(state.country==='PSE'&&v[0]>=2023?'Counterfactual baseline':phase(v[0]))}</td><td>${esc(compositionBasis(D,state.country,v[0]))}</td></tr>`;}).join('')+'</tbody></table>';
  }
  function renderFactors(){
    const list=factorRows(D,state,$('factor-search').value,$('factor-group').value,$('factor-status').value),all=factorRows(D,state),used=all.filter(r=>r.used).length;
    if($('composition-use-note'))$('composition-use-note').textContent=state.country==='WORLD'?'Additional allocation input now in use: GHSL sector-volume paths for 191 historical and 189 future country series. This source allocates the retained Total; it is outside the 49 fitted-model predictor candidates.':'Additional GHSL allocation for '+name(state.country)+': '+(D.countries[state.country].flags.dynamic_history?'2015/2020 historical volume path used':'historical path retains v16')+'; '+(D.countries[state.country].flags.dynamic_future?'2020/2025/2030 projected volume path used':'future path retains v16')+'. The 2020 sector anchors are preserved.';
    $('factor-summary').innerHTML=`<strong>${used} of ${D.factors.length} candidates ${state.country==='WORLD'?'used somewhere in the country roster':'used for '+esc(name(state.country))}.</strong> ${list.length} shown. Static backgrounds and genuinely annual signals have separate roles.`;
    $('factor-table').innerHTML='<table><thead><tr><th>Factor</th><th>Mechanism</th><th>Period / background role</th><th>Annual timing role</th><th>Historical support</th><th>Source & quality</th></tr></thead><tbody>'+list.map(({f,use,isPrior,used,indirect})=>{
      const global=state.country==='WORLD',role=isPrior?'Horizontal prior':use[0]?(use[3]?'Static context':'Period change'):'Not used';
      const period=indirect?(use[0]?'Combined construction lag':'Not used'):global?(f.role==='horizontal_prior_not_fitted_feature'?'Horizontal prior':f.period_countries+' / 195 countries'):role;
      const timing=indirect?(use[1]?'With construction signal':'Not used'):global?f.timing_countries+' / 195 countries':use[1]?'Annual timing':'Not used';
      const source=/^https?:\/\//.test(f.url)?`<a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.source)} ↗</a>`:esc(f.source);
      return `<tr><td class="factor-name">${esc(f.label)}<small>${esc(f.id)}</small><details><summary>Definition & limitations</summary><p>${esc(f.temporal.replace(/_/g,' '))}</p><p>${esc(f.limits)}</p></details></td><td>${esc(f.group_label)}</td><td class="${used?'used-word':'not-used'}">${esc(period)}</td><td class="${use[1]?'used-word':'not-used'}">${esc(timing)}</td><td>${global?'See country selection':isPrior?'Endpoint trend':use[3]?(use[2]?'Static snapshot':'No admitted context'):use[2]+' / 5 intervals'}</td><td class="source-cell">${source}<div class="quality">${esc(f.quality.replace(/_/g,' '))}</div></td></tr>`;
    }).join('')+'</tbody></table>';
  }
  function render(){state=normalizeSelection(state,D);$('country').value=state.country;$('start-year').value=state.start;$('end-year').value=state.end;$('chart-view').value=state.view;$('unit').value=state.unit;$('show-range').checked=state.range;root.document.querySelectorAll('[data-sector]').forEach(el=>{const active=el.dataset.sector===state.sector;el.classList.toggle('active',active);el.setAttribute('aria-pressed',String(active));});renderMetrics();renderChart();renderAnnual();renderFactors();saveURL();}
  const chart=$('chart');let dragSelection=null;
  function setEndpoint(endpoint,year,focus=false){
    const next=moveEndpoint(state,endpoint,year);if(next.start===state.start&&next.end===state.end)return;
    state=next;$('start-year').value=state.start;$('end-year').value=state.end;renderMetrics();renderChart();renderAnnual();saveURL();readout(state[endpoint]);
    if(focus)chart.querySelector(`[data-handle="${endpoint}"]`)?.focus({preventScroll:true});
  }
  function pointerYear(e){
    const svg=chart.querySelector('svg'),rect=svg.getBoundingClientRect(),a=svg.querySelector('[data-region="backcast"]'),b=svg.querySelector('[data-region="forecast"]');
    const left=Number(a.getAttribute('x')),right=Number(b.getAttribute('x'))+Number(b.getAttribute('width'));
    return yearAtPlotX((e.clientX-rect.left)*svg.viewBox.baseVal.width/rect.width,left,right-left);
  }
  chart.addEventListener('pointerdown',e=>{
    const handle=e.target.closest('[data-handle]');if(!handle||e.button!==0||dragSelection)return;
    e.preventDefault();dragSelection={endpoint:handle.dataset.handle,pointerId:e.pointerId};chart.classList.add('is-dragging');chart.setPointerCapture(e.pointerId);handle.focus({preventScroll:true});
  });
  chart.addEventListener('pointermove',e=>{if(dragSelection?.pointerId===e.pointerId){e.preventDefault();setEndpoint(dragSelection.endpoint,pointerYear(e));}});
  function finishDrag(e){
    if(dragSelection?.pointerId!==e.pointerId)return;
    const endpoint=dragSelection.endpoint;if(e.type==='pointerup')setEndpoint(endpoint,pointerYear(e));
    dragSelection=null;chart.classList.remove('is-dragging');if(chart.hasPointerCapture(e.pointerId))chart.releasePointerCapture(e.pointerId);
    chart.querySelector(`[data-handle="${endpoint}"]`)?.focus({preventScroll:true});readout(state[endpoint]);
  }
  ['pointerup','pointercancel','lostpointercapture'].forEach(event=>chart.addEventListener(event,finishDrag));
  chart.addEventListener('keydown',e=>{
    const handle=e.target.closest('[data-handle]');if(!handle)return;
    const endpoint=handle.dataset.handle,offset={ArrowLeft:-1,ArrowDown:-1,ArrowRight:1,ArrowUp:1,PageDown:-5,PageUp:5}[e.key];
    const year=e.key==='Home'?2015:e.key==='End'?2030:offset?state[endpoint]+offset:null;
    if(year!==null){e.preventDefault();setEndpoint(endpoint,year,true);}
  });
  $('country').innerHTML='<option value="WORLD">Global · core 194 countries</option>'+Object.values(D.countries).sort((a,b)=>name(a.id).localeCompare(name(b.id))).map(c=>`<option value="${c.id}">${esc(name(c.id))} (${c.id})${c.supplement?' · supplement':''}</option>`).join('');
  $('start-year').innerHTML=Array.from({length:15},(_,j)=>`<option>${2015+j}</option>`).join('');$('end-year').innerHTML=Array.from({length:15},(_,j)=>`<option>${2016+j}</option>`).join('');
  $('country').addEventListener('change',e=>{state.country=e.target.value;render();});
  root.document.querySelectorAll('[data-sector]').forEach(b=>b.addEventListener('click',()=>{state.sector=b.dataset.sector;render();}));
  $('start-year').addEventListener('change',e=>{state.start=Number(e.target.value);if(state.start>=state.end)state.end=state.start+1;render();});
  $('end-year').addEventListener('change',e=>{state.end=Number(e.target.value);if(state.end<=state.start)state.start=state.end-1;render();});
  $('chart-view').addEventListener('change',e=>{state.view=e.target.value;render();});$('unit').addEventListener('change',e=>{state.unit=e.target.value;render();});$('show-range').addEventListener('change',e=>{state.range=e.target.checked;renderChart();saveURL();});
  ['factor-search','factor-group','factor-status'].forEach(id=>$(id).addEventListener(id==='factor-search'?'input':'change',renderFactors));
  $('download-country').addEventListener('click',()=>download(makeCSV(series(D,state.country),state.country,name(state.country),state.country==='WORLD'||D.countries[state.country]?.core,state.start,state.end,D),`gfa_${state.country}_2015_2030_${D.version}.csv`,'text/csv;charset=utf-8;'));
  $('download-chart').addEventListener('click',()=>{const svg=buildSVG(series(D,state.country),state,units(series(D,state.country),state.sector,state.unit),1060,name(state.country));download(svg,`gfa_${state.country}_${state.sector}_${state.view}_${state.start}_${state.end}.svg`,'image/svg+xml;charset=utf-8;');});
  $('share-view').addEventListener('click',async()=>{try{await root.navigator.clipboard.writeText(root.location.href);toast('View link copied.');}catch{toast('This view is saved in the browser address. Copy that address to share it.');}});
  $('parameter-table').innerHTML='<table><thead><tr><th>Shared coefficient</th><th>Value</th></tr></thead><tbody>'+Object.entries(D.coefficients).map(([n,v])=>`<tr><td>${esc(n.replace(/_/g,' '))}</td><td class="num">${number(v,6)}</td></tr>`).join('')+'</tbody></table>';
  let resizeTimer;root.addEventListener('resize',()=>{root.clearTimeout(resizeTimer);resizeTimer=root.setTimeout(renderChart,120);});
  root.addEventListener('popstate',()=>{const p=new URLSearchParams(root.location.search);state=normalizeSelection({country:p.get('country')||'WORLD',sector:p.get('sector'),start:p.get('from'),end:p.get('to'),view:p.get('view'),unit:p.get('unit'),range:p.get('range')!=='off'},D);render();});
  render();
})(typeof window==='undefined'?globalThis:window);
