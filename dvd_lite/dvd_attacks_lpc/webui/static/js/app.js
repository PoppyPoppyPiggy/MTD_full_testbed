async function fetchJSON(url, opts={}) {
    try {
      const res = await axios({url, method: opts.method||'get', data: opts.body||null});
      return res.data;
    } catch (e) {
      console.error(e);
      return null;
    }
  }
  
  function fmt(x) {
    if (x===null || x===undefined) return 'NA';
    if (typeof x==='number') return Number.isInteger(x)? x.toString() : x.toFixed(3);
    return x;
  }
  
  async function loadBus() {
    const data = await fetchJSON('/api/bus?limit=500');
    if (!data) return;
    document.getElementById('busMtime').textContent = data.mtime || '-';
    const tbody = document.querySelector('#busTable tbody');
    tbody.innerHTML = '';
    (data.rows||[]).forEach(r=>{
      const tr=document.createElement('tr');
      tr.innerHTML = `<td>${fmt(r.ts)}</td><td>${r.tag}</td><td>${r.kv}</td>`;
      tbody.appendChild(tr);
    });
  }
  
  async function loadEffects() {
    const data = await fetchJSON('/api/effects');
    if (!data) return;
    document.getElementById('tlMtime').textContent = data.mtime || '-';
    const t=data.t || [];
    const traces = [
      {x:t, y:data.loss_pct||[], name:'loss_pct(%)', mode:'lines'},
      {x:t, y:data.delay_ms||[], name:'delay_ms', mode:'lines'},
      {x:t, y:data.jitter_ms||[], name:'jitter_ms', mode:'lines'},
      {x:t, y:data.dup_pct||[], name:'dup_pct(%)', mode:'lines'}
    ];
    Plotly.newPlot('chartEffects', traces, {margin:{t:20}, legend:{orientation:'h'}});
  }
  
  async function loadNS3() {
    const data = await fetchJSON('/api/ns3');
    if (!data) return;
    document.getElementById('ns3Mtime').textContent = data.mtime || '-';
    const el = document.getElementById('ns3Stats');
    const m = data.metrics || {};
    const keys = Object.keys(m);
    if (!keys.length) { el.textContent='-'; return; }
    el.innerHTML = keys.map(k=>`<div><b>${k}</b> : ${fmt(m[k])}</div>`).join('');
  }
  
  async function loadScore() {
    const data = await fetchJSON('/api/score');
    if (!data) return;
    document.getElementById('scoreMtime').textContent = data.mtime || '-';
    const el = document.getElementById('scoreStats');
    const s = data.score || {};
    if (!Object.keys(s).length) { el.textContent='-'; return; }
    const c=s.cti||{}, m=s.mtd||{};
    let html = `
    <div><h4>CTI</h4>
      <div>MTD events: ${fmt(c.events_mtd)} / CTI ip_change: ${fmt(c.events_cti)}</div>
      <div>detect_latency_mean_s: ${fmt(c.detect_latency_mean_s)}</div>
      <div>followup_latency_mean_s: ${fmt(c.followup_latency_mean_s)}</div>
      <div>ip_tracking_accuracy: ${fmt(c.ip_tracking_accuracy)}</div>
      <div>port_tracking_accuracy: ${fmt(c.port_tracking_accuracy)}</div>
    </div>
    <div><h4>MTD</h4>
      <div>disruption_window_mean_s: ${fmt(m.disruption_window_mean_s)}</div>
      <div>impair_loss_area_pct_x_s: ${fmt(m.impair_loss_area_pct_x_s)}</div>
      <div>impair_delay_area_ms_x_s: ${fmt(m.impair_delay_area_ms_x_s)}</div>
      <div>impair_jitter_area_ms_x_s: ${fmt(m.impair_jitter_area_ms_x_s)}</div>
    </div>`;
    el.innerHTML = html;
  }
  
  async function loadDataset() {
    const data = await fetchJSON('/api/dataset?limit=50');
    if (!data) return;
    document.getElementById('dsMtime').textContent = data.mtime || '-';
    const thead=document.querySelector('#dsTable thead');
    const tbody=document.querySelector('#dsTable tbody');
    thead.innerHTML = ''; tbody.innerHTML='';
    const header = data.header || [];
    if (header.length) {
      const tr=document.createElement('tr');
      tr.innerHTML = header.map(h=>`<th>${h}</th>`).join('');
      thead.appendChild(tr);
    }
    (data.rows||[]).forEach(r=>{
      const tr=document.createElement('tr');
      tr.innerHTML = r.map(c=>`<td>${c}</td>`).join('');
      tbody.appendChild(tr);
    });
  }
  
  async function refreshAll() {
    await Promise.all([loadBus(), loadEffects(), loadNS3(), loadScore(), loadDataset()]);
  }
  
  document.getElementById('refreshBtn').addEventListener('click', refreshAll);
  
  let timer = setInterval(refreshAll, 3000);
  document.getElementById('autoRefresh').addEventListener('change', (e)=>{
    if (e.target.checked) { timer=setInterval(refreshAll,3000); }
    else { clearInterval(timer); }
  });
  
  document.getElementById('runBtn').addEventListener('click', async ()=>{
    const N   = parseInt(document.getElementById('paramN').value||'50',10);
    const RUN = document.getElementById('paramRun').value;
    const RATE= parseInt(document.getElementById('paramRate').value||'30',10);
    const Php = parseInt(document.getElementById('paramPhp').value||'50',10);
    const Ffp = parseInt(document.getElementById('paramFfp').value||'50',10);
    const Wait= parseFloat(document.getElementById('paramWait').value||'0.5');
    const res = await fetchJSON('/api/run', {method:'post', body:{N, RUN_NS3: Number(RUN), ATK_RATE_MBPS: RATE, PORT_HOP_PROB: Php, FOLLOW_FLOOD_PROB: Ffp, CTI_WAIT_S: Wait}});
    const el = document.getElementById('runMsg');
    el.textContent = res && res.ok ? `started pid=${res.pid}` : `failed: ${res?res.error:'unknown'}`;
  });
  
  document.getElementById('killBtn').addEventListener('click', async ()=>{
    const res = await fetchJSON('/api/kill', {method:'post'});
    const el = document.getElementById('runMsg');
    el.textContent = res && res.ok ? `killed pid=${res.killed}` : `failed: ${res?res.error:'no pid'}`;
  });
  
  // 첫 로드
  refreshAll();
  