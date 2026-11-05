'use strict';
const API_BASE = location.hostname === 'leoq77777.github.io' ? 'https://43.166.2.103.sslip.io/nbeta' : '';
let DATA_ROOT = 'data';
const $ = (s, root=document) => root.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num = v => v !== null && v !== '' && v !== undefined && Number.isFinite(+v);
const fmt = (v,d=1) => num(v) ? (+v).toFixed(d) : '—';
const signed = (v,d=1) => num(v) ? `${+v>0?'+':''}${(+v).toFixed(d)}` : '—';
const pct = v => num(v) ? `${(+v*100).toFixed(+v<.01 && +v>0 ? 1 : 0)}%` : '—';
const state = {view:'rankings', conf:'League', sort:'rank', desc:false, query:'', team:'OKC', winFilter:'all'};
let D, teams, logo, tooltip;
const teamLink = ab => `#team/${encodeURIComponent(ab)}`;
function teamName(ab,detail=true){const t=teams.get(ab);return `<a class="team-name" title="${esc(t?.last_game||'')}" href="${teamLink(ab)}">${logo.get(ab)?`<img src="${esc(logo.get(ab))}" alt="" loading="lazy">`:''}<span><strong>${esc(t?.name||ab)}</strong>${detail?`<small>${esc(ab)} · ${t.w}–${t.l}</small>`:''}</span></a>`;}
function heading(title,sub='',controls=''){return `<div class="toolbar"><h2>${title}</h2>${sub?`<span class="sub">${sub}</span>`:''}<div class="push"></div>${controls}</div>`;}
const confControl = () => `<div class="segmented" aria-label="Conference">${['League','East','West'].map(c=>`<button data-conf="${c}" class="${state.conf===c?'active':''}" aria-pressed="${state.conf===c}">${c}</button>`).join('')}</div>`;
const filteredTeams = () => D.teams.filter(t=>(state.conf==='League'||t.conf===state.conf)&&`${t.name} ${t.city} ${t.abbr}`.toLowerCase().includes(state.query.toLowerCase()));
function table(headers, rows, label='Data'){return `<div class="table-wrap ${label==='Remaining schedule'?'schedule-detail':''}" tabindex="0" role="region" aria-label="${esc(label)}"><table aria-label="${esc(label)}"><thead><tr>${headers.map(x=>`<th scope="col">${x}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;}
const row = cells => `<tr>${cells.map(c=>`<td>${c}</td>`).join('')}</tr>`;
function prob(v){return `<span class="prob"><span class="mini-bar"><i style="width:${(+v*100).toFixed(2)}%"></i></span><span class="num">${pct(v)}</span></span>`;}
function panel(title,caption,body){return `<section class="panel"><h3>${title}</h3><p class="caption">${caption}</p>${body}</section>`;}
function teamPicker(id,value){return `<select id="${id}" class="team-picker" aria-label="Select team">${[...D.teams].sort((a,b)=>a.city.localeCompare(b.city)).map(t=>`<option value="${t.abbr}" ${t.abbr===value?'selected':''}>${esc(t.city)} ${esc(t.name)}</option>`).join('')}</select>`;}
function render(){
  const parts=location.hash.slice(1).split('/');
  state.view=['rankings','wins','ratings','games','team','model'].includes(parts[0])?parts[0]:'rankings';
  if(parts[1]&&teams.has(parts[1])) state.team=parts[1];
  document.querySelectorAll('#tabs a').forEach(a=>{const active=a.hash===`#${state.view}`;a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
  document.title=`${{rankings:'Rankings',wins:'Win distributions',ratings:'Ratings',games:'Games',team:teams.get(state.team).name,model:'Model & audit'}[state.view]} · n-Beta`;
  tooltip.hidden=true;
  ({rankings:rankings,wins:wins,ratings:ratings,games:games,team:teamView,model:modelView}[state.view])();

}
function rankings(){
  const columns=[['rank','#'],['name','Team / Record'],['rating','Rating'],['rating_d7','7d Δ'],['proj_w','Proj. W'],['vegas_diff','Prior Δ'],['sos','SOS'],['sor','SOR'],['p_playoffs','Playoffs'],['p_title','Title']];
  let ts=filteredTeams().sort((a,b)=>{const result=state.sort==='name'?a.name.localeCompare(b.name):+a[state.sort]-+b[state.sort];return state.desc?-result:result;});
  const heads=columns.map(([key,name])=>`<button data-sort="${key}" aria-label="Sort by ${name}">${name}${state.sort===key?(state.desc?' ↓':' ↑'):''}</button>`);
  const rows=ts.map(t=>row([`<span class="rank">${String(t.rank).padStart(2,'0')}</span>`,teamName(t.abbr),`<span class="rating" title="90% credible interval ±${t.rating_ci90}">${signed(t.rating)}</span>`,`<span class="num ${+t.rating_d7>=0?'positive':'negative'}">${signed(t.rating_d7)}</span>`,`<span class="num" title="80% interval ${t.w_p10}–${t.w_p90}">${fmt(t.proj_w)}</span>`,`<span class="num ${+t.vegas_diff>=0?'positive':'negative'}">${signed(t.vegas_diff)}</span>`,`<span class="num">${signed(t.sos)}</span>`,`<span class="num">${signed(t.sor)}</span>`,prob(t.p_playoffs),prob(t.p_title)]));
  $('#content').innerHTML=heading('League outlook','BAYESIAN RATINGS · 90% CREDIBLE INTERVALS',`${confControl()}<button id="export">Export PNG ↗</button>`)+`<label class="small muted">Find a team <input id="search" type="search" placeholder="City, team or abbreviation" value="${esc(state.query)}"></label><div class="two-col rank-tables section-gap">${rows.length ? (state.conf==='League'&&rows.length>15?table(heads,rows.slice(0,15),'Rankings 1–15')+table(heads,rows.slice(15),'Rankings 16–30'):table(heads,rows,'Team rankings')):'<div class="empty">No teams match your search.</div>'}</div><div class="insight"><span>β</span><div><b>Strength, with uncertainty.</b> Rating is expected points above an average team on a neutral court. Hover a rating for its 90% interval. Projections cover ${D.run[0].schedule_games} listed games; Prior Δ compares partial-schedule wins with unverified preseason totals.</div></div>`;
  $('[type=search]').oninput=e=>{const pos=e.target.selectionStart;state.query=e.target.value;rankings();const el=$('#search');el.focus();el.setSelectionRange(pos,pos);};
  document.querySelectorAll('[data-sort]').forEach(b=>b.onclick=()=>{state.desc=state.sort===b.dataset.sort?!state.desc:b.dataset.sort!=='rank';state.sort=b.dataset.sort;rankings();});
  $('#export').onclick=exportPNG;
}
function svgAt(selector,w=500,h=230,label='Chart'){
  const svg=d3.select(selector).append('svg').attr('class','chart').attr('viewBox',`0 0 ${w} ${h}`).attr('role','img').attr('aria-label',label);
  svg.append('title').text(label);return svg;
}
function tip(sel,text){sel.on('pointermove',(event,d)=>{tooltip.hidden=false;tooltip.textContent=text(d);tooltip.style.left=`${Math.min(event.clientX+12,innerWidth-210)}px`;tooltip.style.top=`${Math.max(5,event.clientY-40)}px`;}).on('pointerleave',()=>tooltip.hidden=true);}
function chartColor(t){
  const c=d3.color(t.color),rgb=c.rgb(),luma=rgb.r*.2126+rgb.g*.7152+rgb.b*.0722;
  if(document.documentElement.dataset.theme==='dark'&&luma<75){const alt=d3.color(t.alt_color).rgb();return alt.r*.2126+alt.g*.7152+alt.b*.0722>90?t.alt_color:c.brighter(1.8).formatHex();}
  return document.documentElement.dataset.theme==='light'&&luma>205?c.darker(1).formatHex():t.color;
}
function distribution(selector,ab,compact=false){
  const t=teams.get(ab), values=D.win_dist.filter(d=>d.abbr===ab).map(d=>({wins:+d.wins,p:+d.p,prior:+d.p_prior}));
  const W=compact?360:550,H=compact?150:240,m={l:32,r:15,t:15,b:27};
  const svg=svgAt(selector,W,H,`${t.name} projected wins probability distribution`);
  const x=d3.scaleLinear().domain([0,d3.max(values,d=>d.wins)]).range([m.l,W-m.r]);
  const y=d3.scaleLinear().domain([0,d3.max(values,d=>Math.max(d.p,d.prior))*1.15||1]).range([H-m.b,m.t]);
  svg.append('rect').attr('x',x(+t.w_p10)).attr('width',x(+t.w_p90)-x(+t.w_p10)).attr('y',m.t).attr('height',H-m.t-m.b).attr('fill','var(--accent)').attr('opacity',.07);
  const bars=svg.selectAll('rect.bar').data(values).join('rect').attr('class','bar').attr('x',d=>x(d.wins)).attr('y',d=>y(d.p)).attr('width',Math.max(1,(W-m.l-m.r)/values.length-1)).attr('height',d=>y(0)-y(d.p)).attr('fill',chartColor(t)).attr('opacity',.85);
  tip(bars,d=>`${d.wins} wins · ${(d.p*100).toFixed(2)}%`);
  svg.append('path').datum(values).attr('d',d3.line().x(d=>x(d.wins)).y(d=>y(d.prior))).attr('fill','none').attr('stroke','var(--muted)').attr('stroke-dasharray','2 2').attr('opacity',.7);
  svg.append('g').attr('transform',`translate(0,${H-m.b})`).call(d3.axisBottom(x).ticks(compact?5:8).tickSize(0).tickPadding(9));
  svg.append('g').attr('transform',`translate(${m.l},0)`).call(d3.axisLeft(y).ticks(3).tickFormat(d3.format('.0%')).tickSize(0));
  svg.append('line').attr('x1',x(+t.vegas_total)).attr('x2',x(+t.vegas_total)).attr('y1',m.t).attr('y2',y(0)).attr('stroke','var(--muted)').attr('stroke-dasharray','3 3');
  svg.append('circle').attr('cx',x(+t.proj_w)).attr('cy',H-m.b).attr('r',4).attr('fill','var(--accent)');
}
function wins(){
  const ts=filteredTeams().filter(t=>state.winFilter==='all'||(state.winFilter==='above'?+t.vegas_diff>=0:+t.vegas_diff<0));
  $('#content').innerHTML=heading('The range of possible','REGULAR SEASON · 10TH–90TH PERCENTILE',`${confControl()}<select id="win-filter" aria-label="Compare preseason total"><option value="all">All projections</option><option value="above">Above preseason total</option><option value="below">Below preseason total</option></select>`)+`<div class="legend"><span><i></i>Mean projected wins</span><span><i class="band"></i>80% interval</span><span><i class="dashed"></i>Preseason total & prior PMF</span></div><div class="dist-grid">${ts.map(t=>`<section class="panel"><div class="chart-title">${teamName(t.abbr,false)}<div class="dist-meta">${fmt(t.proj_w)} W<small>${t.w_p10}–${t.w_p90} · 80% interval</small></div></div><div id="dist-${t.abbr}"></div></section>`).join('')}</div>${ts.length?'':'<div class="empty">No teams match this filter.</div>'}`;
  $('#win-filter').value=state.winFilter;$('#win-filter').onchange=e=>{state.winFilter=e.target.value;wins();};
  ts.forEach(t=>distribution(`#dist-${t.abbr}`,t.abbr,true));
}
function historyChart(selector,ab,all=false){
  const W=900,H=320,m={l:42,r:25,t:20,b:32},svg=svgAt(selector,W,H,'Team rating history with 90% credible interval');
  const hist=D.history.map(d=>({...d,date:new Date(d.date+'T12:00:00Z'),rating:+d.rating,lo:+d.rating_lo,hi:+d.rating_hi}));
  const selected=hist.filter(d=>d.abbr===ab); const domainRows=all?hist:selected;
  const extent=d3.extent(hist,d=>d.date);if(+extent[0]===+extent[1])extent[1]=new Date(+extent[1]+86400000);
  const x=d3.scaleTime().domain(extent).range([m.l,W-m.r]),y=d3.scaleLinear().domain([d3.min(domainRows,d=>d.lo)-1,d3.max(domainRows,d=>d.hi)+1]).nice().range([H-m.b,m.t]);
  svg.append('g').attr('class','grid').attr('transform',`translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5).tickSize(-(W-m.l-m.r)).tickFormat(''));
  svg.append('g').attr('transform',`translate(0,${H-m.b})`).call(d3.axisBottom(x).ticks(7).tickFormat(d3.utcFormat('%b %d')).tickSize(0).tickPadding(12));
  svg.append('g').attr('transform',`translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5).tickSize(0).tickPadding(9));
  const line=d3.line().x(d=>x(d.date)).y(d=>y(d.rating));
  if(all) for(const [key,values] of d3.group(hist,d=>d.abbr)) if(key!==ab)svg.append('path').datum(values).attr('d',line).attr('stroke',teams.get(key).color).attr('stroke-width',1).attr('opacity',.3).attr('fill','none');
  svg.append('path').datum(selected).attr('d',d3.area().x(d=>x(d.date)).y0(d=>y(d.lo)).y1(d=>y(d.hi))).attr('fill','var(--accent)').attr('opacity',.1);
  svg.append('path').datum(selected).attr('d',line).attr('stroke','var(--accent)').attr('stroke-width',2.5).attr('fill','none');
  if(!all){
    const performance=D.schedule.filter(g=>g.status==='final'&&(g.home===ab||g.away===ab)).map(g=>({date:new Date(g.date+'T12:00:00Z'),margin:g.home===ab?+g.clean_margin:-g.clean_margin}));
    const yp=d3.scaleLinear().domain([-40,40]).range([H-m.b,m.t]);
    const pts=svg.selectAll('circle.performance').data(performance).join('circle').attr('class','performance').attr('cx',d=>x(d.date)).attr('cy',d=>yp(d.margin)).attr('r',4).attr('fill','none').attr('stroke','var(--muted)').attr('opacity',.8);
    tip(pts,d=>`${d3.utcFormat('%b %d')(d.date)} · clean margin proxy ${signed(d.margin)}`);
    svg.append('g').attr('transform',`translate(${W-m.r},0)`).call(d3.axisRight(yp).ticks(4).tickSize(0));
  }
  const dots=svg.selectAll('circle.rating-point').data(selected).join('circle').attr('class','rating-point').attr('cx',d=>x(d.date)).attr('cy',d=>y(d.rating)).attr('r',3).attr('fill','var(--accent)');tip(dots,d=>`${d3.utcFormat('%b %d')(d.date)} · ${d.rating.toFixed(2)} [${d.lo}, ${d.hi}]`);
}
function ratings(){
  const t=teams.get(state.team);
  $('#content').innerHTML=heading('Strength is a moving target','DYNAMIC STATE-SPACE RATINGS',teamPicker('rating-team',state.team))+panel(`${esc(t.city)} ${esc(t.name)}`,'Selected team with 90% credible band · background lines show the league','<div id="rating-chart"></div>')+`<h3 class="table-section">Posterior & prior</h3>`+table(['Team','Prior','Current','Active','90% CI','7d Δ','Injury synergy'],D.teams.map(t=>row([teamName(t.abbr),fmt(t.rating_prior),signed(t.rating),signed(t.rating_today),`±${fmt(t.rating_ci90)}`,signed(t.rating_d7),fmt(t.synergy_penalty)])),'Rating decomposition');
  historyChart('#rating-chart',state.team,true);$('#rating-team').onchange=e=>{state.team=e.target.value;ratings();};
}
function gameCard(g){const final=g.status==='final', date=new Date(g.tip);return `<article class="panel"><div class="game-head"><span>${esc(g.date)} · ${isNaN(date)?'TBD':date.toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit',timeZone:'America/New_York'})+' ET'}</span><span>${final?'FINAL':'FORECAST'}</span></div><div class="match-row">${teamName(g.away,false)}<span class="score">${final?g.as:pct(1-g.p_home)}</span></div><div class="match-row">${teamName(g.home,false)}<span class="score">${final?g.hs:pct(g.p_home)}</span></div><div class="winbar"><i style="width:${(1-g.p_home)*100}%"></i></div><div class="bar-labels"><span>${g.away} ${pct(1-g.p_home)}</span><span>${g.home} ${pct(g.p_home)}</span></div><div class="game-metrics"><div><span>MODEL / HOME</span><strong>${signed(g.spread)}</strong></div><div><span>MARKET / HOME</span><strong>${signed(g.market_spread)}</strong></div><div><span>EDGE / HOME</span><strong>${signed(g.edge_pts)}${num(g.edge_pts)&&Math.abs(+g.edge_pts)>=1.5?' *':''}</strong></div></div></article>`;}
function games(){
  const date=state.gameDate || D.schedule.find(g=>g.status==='upcoming')?.date || D.run[0].data_through;
  const dates=[...new Set(D.schedule.map(g=>g.date))].sort();state.gameDate=date;
  $('#content').innerHTML=heading('Every game is a distribution','HOME SPREAD: NEGATIVE MEANS FAVORED',`<button id="prev-date" aria-label="Previous day">←</button><input id="game-date" aria-label="Game date" type="date" min="${dates[0]}" max="${dates.at(-1)}" value="${date}"><button id="next-date" aria-label="Next day">→</button>`)+`<div class="game-list">${D.schedule.filter(g=>g.date===date).map(gameCard).join('')}</div>${D.schedule.some(g=>g.date===date)?'':'<div class="empty">No games scheduled on this date.</div>'}<p class="muted small">Market and edge stay blank when no observed market line is supplied. A spread difference alone is not a priced +EV bet.</p>`+panel('Matchup sandbox','Change the teams and home advantage. Uses the same Student-t transform as the Python model.',`<div class="sandbox-controls"><label>Home team${teamPicker('sandbox-home','OKC')}</label><label>Away team${teamPicker('sandbox-away','BOS')}</label><label>Home rating adjustment <input type="range" id="sandbox-adjust" min="-8" max="8" step="0.5" value="0"><output id="adjust-label">0.0 pts</output></label><label><span><input id="sandbox-neutral" type="checkbox">Neutral court</span></label><label><span><input id="sandbox-active" type="checkbox" checked>Apply injury discount</span></label></div><div class="sandbox-result" id="sandbox-result" aria-live="polite"></div>`);
  $('#game-date').onchange=e=>{if(e.target.value){state.gameDate=e.target.value;games();}};
  for(const [id,delta] of [['prev-date',-1],['next-date',1]]) $( '#'+id).onclick=()=>{const d=new Date(state.gameDate+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+delta);state.gameDate=d.toISOString().slice(0,10);games();};
  ['sandbox-home','sandbox-away','sandbox-adjust','sandbox-neutral','sandbox-active'].forEach(id=>$('#'+id).oninput=sandbox);sandbox();
}
function studentTCDF(z,df){
  const integrate=end=>{const n=120,h=end/n;let sum=1+Math.cos(end)**(df-1);for(let i=1;i<n;i++)sum+=(i%2?4:2)*Math.cos(i*h)**(df-1);return sum*h/3;};
  return .5+Math.sign(z)*.5*integrate(Math.atan(Math.abs(z)/Math.sqrt(df)))/integrate(Math.PI/2);
}
function sandbox(){
  const h=teams.get($('#sandbox-home').value),a=teams.get($('#sandbox-away').value),adj=+$('#sandbox-adjust').value;
  $('#adjust-label').textContent=signed(adj)+' pts';
  if(h===a){$('#sandbox-result').textContent='Choose two different teams to forecast a matchup.';return;}
  const active=$('#sandbox-active').checked,neutral=$('#sandbox-neutral').checked;
  const param=k=>+D.params.find(p=>p.key===k).value;
  const margin=+(active?h.rating_today:h.rating)-+(active?a.rating_today:a.rating)+adj+(neutral?0:param('home_court_advantage')+(['DEN','UTA'].includes(h.abbr)?param('altitude_home_bonus'):0));
  const sd=Math.sqrt((param('base_game_sd')*((+h.volatility_mult)+(+a.volatility_mult))/2)**2+(+h.rating_sd)**2+(+a.rating_sd)**2),df=param('student_t_df');
  const p=Math.min(.995,Math.max(.005,studentTCDF(margin/(sd*Math.sqrt((df-2)/df)),df)));
  $('#sandbox-result').innerHTML=`<div><strong>${pct(p)}</strong> ${h.abbr} win</div><span>${a.abbr} ${pct(1-p)}</span><span>Home spread <b>${signed(-margin)}</b></span><span class="muted">Equal rest · no B2B</span>`;
}
function seedChart(selector,t){
  const W=550,H=220,m={l:35,r:12,t:20,b:28},svg=svgAt(selector,W,H,'Conference seed probabilities');const data=Array.from({length:15},(_,i)=>({seed:i+1,p:+t[`seed_${i+1}`]}));
  const x=d3.scaleBand().domain(data.map(d=>d.seed)).range([m.l,W-m.r]).padding(.3),y=d3.scaleLinear().domain([0,d3.max(data,d=>d.p)*1.1||1]).range([H-m.b,m.t]);
  const bars=svg.selectAll('rect').data(data).join('rect').attr('x',d=>x(d.seed)).attr('y',d=>y(d.p)).attr('width',x.bandwidth()).attr('height',d=>y(0)-y(d.p)).attr('fill',d=>d.seed<=6?'var(--accent)':d.seed<=10?chartColor(t):'var(--muted)');tip(bars,d=>`Seed ${d.seed} · ${pct(d.p)}`);
  svg.append('g').attr('transform',`translate(0,${H-m.b})`).call(d3.axisBottom(x).tickSize(0).tickPadding(10));svg.append('g').attr('transform',`translate(${m.l},0)`).call(d3.axisLeft(y).ticks(3).tickFormat(d3.format('.0%')).tickSize(0));
}
function pathChart(selector,t){
  const data=[['Top 6','p_top6'],['Play-in','p_playin'],['Round 1','p_playoffs'],['Round 2','p_r2'],['Conf. finals','p_cf'],['Finals','p_finals'],['Title','p_title']];
  const svg=svgAt(selector,550,245,'Playoff qualification and advancement probabilities');
  data.forEach(([label,key],i)=>{const y=20+i*31;svg.append('text').attr('x',0).attr('y',y+10).text(label);svg.append('rect').attr('x',90).attr('y',y).attr('width',380).attr('height',13).attr('rx',2).attr('fill','var(--line)');svg.append('rect').attr('x',90).attr('y',y).attr('width',380*+t[key]).attr('height',13).attr('rx',2).attr('fill',i===1?chartColor(t):'var(--accent)');svg.append('text').attr('x',540).attr('y',y+11).attr('text-anchor','end').text(pct(t[key]));});
}
function remainingChart(selector,ab){
  const data=D.schedule.filter(g=>g.status!=='final'&&(g.home===ab||g.away===ab)).map(g=>({...g,p:g.home===ab?+g.p_home:1-g.p_home}));
  if(!data.length){$(selector).innerHTML='<p class="muted">No remaining games.</p>';return;}
  const W=900,H=230,m={l:40,r:12,t:15,b:28},svg=svgAt(selector,W,H,'Remaining games win probabilities and trailing 10-game average');
  const x=d3.scaleBand().domain(data.map(g=>g.id)).range([m.l,W-m.r]).padding(.3),y=d3.scaleLinear().domain([0,1]).range([H-m.b,m.t]);
  const bars=svg.selectAll('rect').data(data).join('rect').attr('x',d=>x(d.id)).attr('y',d=>y(d.p)).attr('width',x.bandwidth()).attr('height',d=>y(0)-y(d.p)).attr('fill',chartColor(teams.get(ab)));tip(bars,d=>`${d.date} ${d.away} @ ${d.home} · ${pct(d.p)}`);
  svg.append('line').attr('x1',m.l).attr('x2',W-m.r).attr('y1',y(.5)).attr('y2',y(.5)).attr('stroke','var(--muted)').attr('stroke-dasharray','3 3');
  const avg=data.map((g,i)=>({...g,avg:d3.mean(data.slice(Math.max(0,i-9),i+1),d=>d.p)}));svg.append('path').datum(avg).attr('d',d3.line().x(d=>x(d.id)+x.bandwidth()/2).y(d=>y(d.avg))).attr('fill','none').attr('stroke','var(--accent)').attr('stroke-width',2);
  svg.append('g').attr('transform',`translate(${m.l},0)`).call(d3.axisLeft(y).ticks(4).tickFormat(d3.format('.0%')).tickSize(0));
  svg.append('g').attr('transform',`translate(0,${H-m.b})`).call(d3.axisBottom(x).tickValues(data.filter((_,i)=>i%12===0).map(d=>d.id)).tickFormat(id=>data.find(g=>g.id===id).date.slice(5)).tickSize(0).tickPadding(10));
}
function teamView(){
  const t=teams.get(state.team),gs=D.schedule.filter(g=>g.home===t.abbr||g.away===t.abbr),next=gs.find(g=>g.status==='upcoming');
  const stat=(label,value,note)=>`<div class="stat"><label>${label}</label><strong>${value}</strong><small>${note}</small></div>`;
  const gameRows=(rows,final)=>rows.map(g=>{const home=g.home===t.abbr,p=home?+g.p_home:1-g.p_home;return row([g.date,`${home?'vs':'@'} <a href="${teamLink(home?g.away:g.home)}">${home?g.away:g.home}</a>`,final?`${home?g.hs:g.as}–${home?g.as:g.hs}`:pct(p),signed(home?g.spread:-g.spread),signed(num(g.market_spread)?(home?g.market_spread:-g.market_spread):null),final?signed(home?g.home_delta:g.away_delta):signed(num(g.edge_pts)?(home?g.edge_pts:-g.edge_pts):null),...(final?[signed(home?g.clean_margin:-g.clean_margin)]:[])]);});
  $('#content').innerHTML=heading('Team intelligence','A CLOSER LOOK',teamPicker('team-select',t.abbr))+`<div class="team-heading">${logo.get(t.abbr)?`<img src="${esc(logo.get(t.abbr))}" alt="">`:''}<div><h2>${esc(t.city)} ${esc(t.name)}</h2><p>${t.conf.toUpperCase()} · ${t.div.toUpperCase()} · ${t.w}–${t.l} · #${t.rank} OVERALL</p></div></div><div class="stat-grid">${stat('Rating / 90% CI',signed(t.rating),`±${fmt(t.rating_ci90)} pts · 7d ${signed(t.rating_d7)}`)}${stat('Active rating',signed(t.rating_today),next?`NEXT ${next.date} ${next.away} @ ${next.home}`:'No next game')}${stat('Projected wins',fmt(t.proj_w),`${t.w_p10}–${t.w_p90} · ${gs.length} listed games`)}${stat('Playoffs / Title',pct(t.p_playoffs),`${pct(t.p_title)} championship`)}${stat('Preseason total',fmt(t.vegas_total),`Prior ${signed(t.rating_prior)} · Δ ${signed(t.vegas_diff)}`)}${stat('SOS · SOR',`${signed(t.sos)} / ${signed(t.sor)}`,`SOS #${t.sos_rank} · SOR #${t.sor_rank}`)}</div><div class="two-col">${panel('Win distribution','80% posterior interval · seed total dashed','<div id="team-wins"></div>')}${panel('Playoff path','Top 6 and play-in are separate qualification paths','<div id="team-path"></div>')}${panel('Conference seed','Top 6 direct · 7–10 play-in · 11–15 eliminated','<div id="team-seed"></div>')}${panel('Rating over time','Lime: rating ±90% · hollow dots: clean margin proxy (right axis)','<div id="team-history"></div>')}</div><div class="section-gap">${panel('The road ahead','Game win probabilities · trailing 10-game average in lime','<div id="team-remaining"></div>')}</div><div class="two-col section-gap"><section><h3 class="table-section">Results</h3>${table(['Date','Opponent','Score','Model','Market','Rating Δ','Clean proxy'],gameRows(gs.filter(g=>g.status==='final').reverse(),true),'Team results')}</section><section><h3 class="table-section">Remaining schedule</h3>${table(['Date','Opponent','Win %','Model','Market','Edge'],gameRows(gs.filter(g=>g.status!=='final'),false),'Remaining schedule')}</section></div><h3 class="table-section">Roster & availability</h3><p class="muted small">O/D values are a position-based allocation of seed player value, not measured impact estimates. Injury statuses are snapshot inputs.</p>${table(['Player','Pos','MPG','O-Value','D-Value','Value','Status','Out %','Return'],D.players.filter(p=>p.abbr===t.abbr).sort((a,b)=>b.value-a.value).map(p=>row([esc(p.name),esc(p.pos),fmt(p.mpg),fmt(p.o_value,2),fmt(p.d_value,2),fmt(p.value,2),`<span class="${p.status==='Active'?'muted':'negative'}">${esc(p.status)}</span>`,pct(p.p_out),esc(p.return_date)||'—'])),'Team roster')}`;
  distribution('#team-wins',t.abbr);pathChart('#team-path',t);seedChart('#team-seed',t);historyChart('#team-history',t.abbr);remainingChart('#team-remaining',t.abbr);
  $('#team-select').onchange=e=>location.hash=`team/${e.target.value}`;
}
function calibrationChart(){
  const W=540,H=300,m={l:42,r:25,t:18,b:35},svg=svgAt('#calibration',W,H,'Observed calibration of snapshot predictions');
  const x=d3.scaleLinear().domain([0,1]).range([m.l,W-m.r]),y=d3.scaleLinear().domain([0,1]).range([H-m.b,m.t]);
  svg.append('line').attr('x1',x(0)).attr('x2',x(1)).attr('y1',y(0)).attr('y2',y(1)).attr('stroke','var(--muted)').attr('stroke-dasharray','4 4');
  const data=D.calibration.filter(d=>d.n>0);svg.append('path').datum(data).attr('d',d3.line().x(d=>x(+d.p_mean)).y(d=>y(+d.actual))).attr('fill','none').attr('stroke','var(--accent)').attr('stroke-width',2);
  const points=svg.selectAll('circle').data(data).join('circle').attr('cx',d=>x(+d.p_mean)).attr('cy',d=>y(+d.actual)).attr('r',d=>3+Math.sqrt(d.n)/2).attr('fill','var(--accent)');tip(points,d=>`${d.bin} · predicted ${pct(d.p_mean)} · observed ${pct(d.actual)} · n=${d.n}`);
  svg.append('g').attr('transform',`translate(0,${H-m.b})`).call(d3.axisBottom(x).ticks(5).tickFormat(d3.format('.0%')));svg.append('g').attr('transform',`translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5).tickFormat(d3.format('.0%')));
}
function modelView(){
  const r=D.run[0];
  $('#content').innerHTML=heading('Open the black box','ASSUMPTIONS, INPUTS & OBSERVED PERFORMANCE')+`<div class="audit-callout"><b class="positive">Snapshot research build.</b> The supplied seed data has unverified provenance. Results below are calculated from ${r.games_played} supplied completed games using chronological pregame predictions. Priors may contain information not independently audited. This is not a multi-season out-of-sample backtest.</div><div class="two-col section-gap">${panel('Three layers. One forecast.','BAYESIAN STATE → MATCHUP → POSSIBLE SEASONS',`<div class="prose"><h3>01 / Evolving team strength</h3><p>A Kalman-style filter updates preseason ratings from score-based, soft-capped margins. Team uncertainty shrinks with observations; the league is centered at zero.</p><div class="formula">μ′ = μ + K · (observed margin − expected margin)</div><h3>02 / A heavy-tailed matchup</h3><p>Active roster discounts, home court, altitude, rest and back-to-backs shift the expected margin. A variance-matched Student-t distribution converts it into a win probability.</p><div class="formula">P(home win) = F<sub>t,ν</sub>(Δ / scale)</div><h3>03 / Simulate the whole path</h3><p>Sample uncertain strength once per season, then simulate each listed game, play-in tournament and 2–2–1–1–1 playoff series. Injury recovery is an assumed team-level Weibull horizon; ties use random jitter, not official tiebreakers.</p></div>`)}${panel('Calibration, observed','X: forecast win probability · Y: realized home win rate','<div id="calibration"></div><p class="caption">Point size reflects sample count. Small snapshot bins have substantial sampling uncertainty.</p>')  }</div><h3 class="table-section">Snapshot prequential scorecard</h3>${table(['Model','Scope','Games','Log loss ↓','Brier ↓','Accuracy'],D.backtest.map(b=>row([esc(b.model),esc(b.split),b.games,fmt(b.logloss,4),fmt(b.brier,4),pct(b.acc)])),'Prediction audit')}<div class="two-col section-gap">${panel('Core parameters','Configured values · no cross-validation claim',table(['Parameter','Value','Unit'],D.params.filter(p=>p.group==='core').map(p=>row([esc(p.label),fmt(p.value,3),esc(p.unit)])),'Core parameters'))}${panel('Context factors','Configured assumptions · historical ablation not available',table(['Factor','Value','Unit'],D.params.filter(p=>p.group==='factor').map(p=>row([esc(p.label),fmt(p.value,2),esc(p.unit)])),'Context factors'))}</div><section class="panel section-gap prose"><h3>Data coverage & known limits</h3><p>Data through ${esc(r.data_through)} · build ${esc(r.as_of)} · random seed ${r.random_seed}. ${r.schedule_games} games listed versus ${r.expected_schedule_games} expected; ${r.missing_games} games are not represented. Win projections and loss counts follow the supplied schedule, so a partial-schedule projection is not directly comparable with an 82-game preseason total.</p><p><b>Game data:</b> ${esc(r.data_source)}. <b>Injuries:</b> ${esc(r.injury_source)}. The offline build does not refresh scores. <b>Margins:</b> score-based proxy; raw lineup stints are not supplied. <b>Player O/D:</b> position priors. <b>Markets:</b> only independently supplied market_spread observations; missing lines stay null. No market performance or expected betting value is claimed.</p><p>Current injury information is only used for future forecasts. Historical injury-adjusted priors and player-level return-date survival models require additional source data. Published intervals describe this model, not every source of uncertainty.</p></section><div class="download-links">${['teams','schedule','win_dist','history','players','params','backtest','calibration','run'].map(n=>`<a href="${DATA_ROOT}/${n}.csv" download>${n}.csv ↙</a>`).join('')}</div>`;
  calibrationChart();
}
async function exportPNG(){
  const button=$('#export');button.disabled=true;button.textContent='Rendering…';
  try{
    const canvas=document.createElement('canvas');canvas.width=1800;canvas.height=1230;const c=canvas.getContext('2d');c.fillStyle='#111713';c.fillRect(0,0,1800,1230);
    c.fillStyle='#c4f36b';c.font='bold 42px Georgia';c.fillText('nβ / NBA PROBABILITY LAB',50,70);c.fillStyle='#f0f1e9';c.font='54px Georgia';c.fillText('Beyond the record.',50,145);c.fillStyle='#a2afa3';c.font='18px monospace';c.fillText(`${D.run[0].season} · ${D.run[0].n_sims.toLocaleString()} simulations · data through ${D.run[0].data_through}`,50,187);
    const ordered=[...D.teams].sort((a,b)=>a.rank-b.rank);
    for(let col=0;col<3;col++){
      const x=50+col*580;c.font='16px monospace';c.fillStyle='#a2afa3';c.textAlign='left';c.fillText('RK  TEAM',x,250);
      c.textAlign='right';c.fillText('RTG',x+340,250);c.fillText('WINS',x+440,250);c.fillText('TITLE',x+535,250);
      for(let i=0;i<10;i++){
        const t=ordered[col*10+i],y=302+i*75;c.fillStyle='#303d31';c.fillRect(x,y+42,545,1);
        c.fillStyle='#f0f1e9';c.font='20px monospace';c.textAlign='left';c.fillText(`${String(t.rank).padStart(2)}  ${t.abbr}`,x,y);
        c.fillStyle='#c4f36b';c.textAlign='right';c.fillText(signed(t.rating),x+340,y);c.fillText(fmt(t.proj_w),x+440,y);c.fillText(pct(t.p_title),x+535,y);
        c.fillStyle='#a2afa3';c.font='14px monospace';c.textAlign='left';c.fillText(`${t.city} ${t.name} · ${t.w}–${t.l}`,x+40,y+24);
      }
    }
    c.fillStyle='#a2afa3';c.font='17px monospace';c.fillText(`Seed snapshot · ${D.run[0].schedule_games} listed games · partial schedule · unverified source`,50,1130);c.fillText('Probability is a perspective, not a promise. / n-Beta',50,1170);
    const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));if(!blob)throw Error('PNG generation failed');const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='n-beta-rankings.png';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(e){button.textContent='Export failed · retry';console.error(e);return;}finally{button.disabled=false;}
  button.textContent='Export PNG ↗';
}
async function init(){
  try{document.documentElement.dataset.theme=localStorage.getItem('nbeta-theme')||'dark';}catch{}
  $('#theme').onclick=()=>{const t=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=t;try{localStorage.setItem('nbeta-theme',t);}catch{}if(D)render();};
  try{
    const names=['run','teams','schedule','win_dist','history','players','params','backtest','calibration','logos'];
    if (API_BASE) {
      const current=await fetch(`${API_BASE}/data/run.json`,{cache:'no-store'});
      if(!current.ok)throw Error(`backend snapshot: HTTP ${current.status}`);
      const snapshot=(await current.json())[0]?.snapshot_id;
      if(!/^[0-9TZ-]+[a-f0-9]{8}$/.test(snapshot||''))throw Error('Invalid backend snapshot version');
      DATA_ROOT=`${API_BASE}/snapshots/${snapshot}/data`;
    }
    const results=await Promise.all(names.map(async name=>{const res=await fetch(`${DATA_ROOT}/${name}.json`);if(!res.ok)throw Error(`${name}: HTTP ${res.status}`);return res.json();}));D=Object.fromEntries(names.map((n,i)=>[n,results[i]]));
    const footerLink=document.querySelector('.site-foot a[download]');if(footerLink)footerLink.href=`${DATA_ROOT}/teams.csv`;
    if(!D.run.length||D.teams.length!==30||!D.history.length)throw Error('Incomplete model snapshot');
    teams=new Map(D.teams.map(t=>[t.abbr,t]));logo=new Map(D.logos.map(l=>[l.abbr,l.src]));tooltip=document.createElement('div');tooltip.className='chart-tip';tooltip.hidden=true;document.body.append(tooltip);
    const r=D.run[0];$('#run-stamp').innerHTML=`<span class="dot"></span>SEASON ${esc(r.season)}<strong>${(+r.n_sims).toLocaleString()}<small> simulations</small></strong>DATA THROUGH ${esc(r.data_through)}<br>${r.games_played} FINAL · ${r.games_left} REMAINING`;
    $('#data-notice').innerHTML=`<b>${r.score_source?'SCORE FEED':'SEED SNAPSHOT'}</b> / ${r.schedule_games} listed games · ${r.missing_games} unlisted · ${esc(r.margin_method)}${r.score_checked_at?` · scores checked ${esc(r.score_checked_at)} UTC`:''}${r.score_unresolved_games?` · ${r.score_unresolved_games} earlier games unresolved`:''} · <a href="#model">View data audit ↗</a>`;
    document.addEventListener('click',event=>{const b=event.target.closest('[data-conf]');if(b){state.conf=b.dataset.conf;render();}});
    window.addEventListener('hashchange',render);render();
  }catch(e){$('#content').innerHTML=`<div class="error"><h2>Snapshot unavailable</h2><p>${esc(e.message)}</p><p>Serve this directory over HTTP, or rebuild the data with <code>python -m pipeline.build_daily</code>.</p><button id="retry">Retry loading</button></div>`;$('#retry').onclick=()=>location.reload();$('#run-stamp').textContent='DATA LOAD FAILED';}
}
init();
