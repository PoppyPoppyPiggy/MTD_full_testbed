async function jget(url) {
  const r = await fetch(url);
  return await r.json();
}
async function jpost(url, body) {
  const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body||{})});
  return await r.json();
}

function el(id){ return document.getElementById(id); }

function renderFiles(data){
  const div = document.getElementById('files');
  if(!data.ok){ div.innerHTML = '<em>error</em>'; return; }
  let html = '<table><tr><th>name</th><th>exists</th><th>size</th><th>mtime</th></tr>';
  for(const f of data.files){
    const dt = f.mtime ? new Date(f.mtime*1000).toLocaleString() : '-';
    html += `<tr><td>${f.name}</td><td>${f.exists}</td><td>${f.size}</td><td>${dt}</td></tr>`;
  }
  html += '</table>';
  div.innerHTML = html;
}

function renderCTI(data){
  const div = document.getElementById('cti');
  const kv = data.cti || {};
  let html = '';
  for(const k of Object.keys(kv)){
    html += `<span class="pill">${k}=${kv[k]}</span>`;
  }
  div.innerHTML = html || '<em>no cti</em>';
}

function renderBus(data){
  const t = document.getElementById('bus');
  const rows = data.rows || [];
  let html = '<tr><th>epoch_ms</th><th>tag</th><th>meta</th></tr>';
  for(const r of rows){
    html += `<tr><td>${r.t}</td><td>${r.tag}</td><td>${r.meta}</td></tr>`;
  }
  t.innerHTML = html;
}

function renderEffects(data){
  const div = document.getElementById('effects');
  const rows = data.rows || [];
  if(rows.length===0){ div.innerHTML = '<em>empty</em>'; return; }
  // 간단 스파크라인(손실/지연/지터/레이트만)
  const xs = rows.map(r=>r.t||r.time||0);
  function col(k){ return rows.map(r=>Number(r[k]||0)); }
  const loss = col('loss_pct'), delay=col('delay_ms'), jitter=col('jitter_ms'), rate=col('rate_limit_mbps');

  // 텍스트형 미니 테이블
  let html = '<table><tr><th>t</th><th>loss%</th><th>delay(ms)</th><th>jitter(ms)</th><th>rate(mbps)</th></tr>';
  for(let i=0;i<Math.min(30, rows.length);i++){
    const r = rows[i];
    html += `<tr><td>${r.t||r.time}</td><td>${r.loss_pct||0}</td><td>${r.delay_ms||0}</td><td>${r.jitter_ms||0}</td><td>${r.rate_limit_mbps||0}</td></tr>`;
  }
  html += '</table>';
  div.innerHTML = html;
}

function renderNs3(data){
  const div = document.getElementById('ns3');
  const rows = data.rows || [];
  if(rows.length===0){ div.innerHTML = '<em>empty</em>'; return; }
  let html = '<table><tr><th>metric</th><th>value</th><th>unit</th></tr>';
  for(const r of rows){
    html += `<tr><td>${r.metric}</td><td>${r.value}</td><td>${r.unit}</td></tr>`;
  }
  html += '</table>';
  div.innerHTML = html;
}

function renderScore(data){
  const pre = document.getElementById('score');
  pre.textContent = JSON.stringify(data.score || {}, null, 2);
}

function renderDataset(data){
  const div = document.getElementById('dataset');
  if(!(data.rows)||data.rows.length===0){ div.innerHTML = '<em>empty</em>'; return; }
  let html = '<table><tr>';
  for(const c of data.cols){ html += `<th>${c}</th>`; }
  html += '</tr>';
  for(const row of data.rows){
    html += '<tr>';
    for(const c of data.cols){ html += `<td>${row[c]}</td>`; }
    html += '</tr>';
  }
  html += '</table>';
  div.innerHTML = html;
}

async function refreshAll(){
  const [m, cti, bus, eff, ns3, sc, log, dset] = await Promise.all([
    jget('/api/metrics'),
    jget('/api/cti'),
    jget('/api/bus?limit=500'),
    jget('/api/effects'),
    jget('/api/ns3'),
    jget('/api/score'),
    jget('/api/runlog'),
    jget('/api/dataset?limit=50')
  ]);
  renderFiles(m);
  renderCTI(cti);
  renderBus(bus);
  renderEffects(eff);
  renderNs3(ns3);
  renderScore(sc);
  el('runlog').textContent = (log.lines||[]).join('\n');
  renderDataset(dset);
}

document.getElementById('btnRebuild').onclick = async ()=>{
  await jget('/api/timeline/rebuild');
  await refreshAll();
};
document.getElementById('btnRefresh').onclick = refreshAll;
document.getElementById('btnStream').onclick = async ()=>{
  await jpost('/api/run/stream', {});
  setTimeout(refreshAll, 1500);
};
document.getElementById('btnCollect').onclick = async ()=>{
  await jpost('/api/run/collect', { N: 50, RUN_NS3: 1, ATK_RATE_MBPS: 30, SIM_TIME: 60 });
  setTimeout(refreshAll, 3000);
};

refreshAll();
setInterval(refreshAll, 4000);
