<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Google SSR Actions - 订阅聚合</title>
  <style>
    :root { --bg:#0f172a; --panel:#0b1220; --muted:#94a3b8; --card:#111827; --accent:#60a5fa; --ok:#10b981; --bad:#ef4444; }
    body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; margin:0; background:linear-gradient(135deg,#0f172a,#111827); color:#e5e7eb; }
    .wrap { max-width: 1200px; margin: 0 auto; padding: 28px; }
    .header { display:flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px; }
    .subtitle { color: var(--muted); margin-top: 4px; }
    .stats { display:grid; grid-template-columns: repeat(auto-fit, minmax(180px,1fr)); gap: 12px; margin: 16px 0 24px; }
    .stat { background: var(--panel); border:1px solid #1f2937; border-radius:12px; padding:16px; text-align:center; box-shadow: 0 8px 20px rgba(0,0,0,.2); }
    .stat .num { font-size: 22px; font-weight: 800; color:#fff; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
    .card { background: var(--card); border: 1px solid #1f2937; border-radius: 16px; padding: 18px; box-shadow: 0 10px 24px rgba(0,0,0,.25); }
    .card-wide { grid-column: 1 / -1; }
    .card h3 { margin: 0 0 12px; font-size: 17px; color:#fff; border-left:3px solid var(--accent); padding-left:10px; }
    code { background:#0b1220; padding: 2px 6px; border-radius: 6px; border: 1px solid #1f2937; color:#d1d5db; }
    small { color: var(--muted); }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
    table { color:#e5e7eb; width:100%; border-collapse:collapse; display:block; overflow:auto; max-height:720px; }
    thead, tbody { display: table; width: 100%; table-layout: fixed; }
    tbody { display: block; max-height: 660px; overflow: auto; scrollbar-gutter: stable; }
    th,td { padding:8px 10px; border-bottom:1px solid #1f2937; word-break: break-all; }
    /* 固定列宽，保证表头与内容对齐 */
    th:nth-child(1), td:nth-child(1) { width: 24%; }
    th:nth-child(2), td:nth-child(2) { width: 6%; text-align:center; }
    th:nth-child(3), td:nth-child(3) { width: 8%; text-align:right; }
    th:nth-child(4), td:nth-child(4) { width: 14%; }
    th:nth-child(5), td:nth-child(5) { width: 15%; }
    th:nth-child(6), td:nth-child(6) { width: 8%; text-align:right; }
    th:nth-child(7), td:nth-child(7) { width: 7%; text-align:right; }
    th:nth-child(8), td:nth-child(8) { width: 9%; }
    th:nth-child(9), td:nth-child(9) { width: 9%; }
    th { color:#cbd5e1; text-align:left; background:#0b1220; position:sticky; top:0; }
    tbody tr:nth-child(even) { background: rgba(31,41,55,.35); }
    tbody tr:hover { background: rgba(59,130,246,.15); }
    .ok { color: var(--ok); }
    .bad { color: var(--bad); }
    .chart { background: var(--panel); border:1px solid #1f2937; border-radius:12px; padding:12px; margin-top:16px; }
    .pill { display:inline-block; padding:2px 8px; border-radius:9999px; font-size:12px; border:1px solid #1f2937; }
    /* Auth overlay */
    .auth-mask { position: fixed; inset:0; display:flex; align-items:center; justify-content:center; backdrop-filter: blur(12px); background: rgba(2,6,23,0.55); z-index: 50; }
    .auth-card { width: 92%; max-width: 380px; background: radial-gradient(120% 120% at 10% 10%, #0b1220 0%, #0a0f1c 60%, #0b1220 100%);
      border:1px solid #1f2937; border-radius: 16px; padding: 18px; box-shadow: 0 20px 40px rgba(0,0,0,.35);
    }
    .auth-title { margin:0 0 8px 0; font-size: 18px; color:#e5e7eb; }
    .auth-sub { margin:0 0 12px 0; color:#94a3b8; font-size: 13px; }
    .auth-input { width:100%; padding:10px 12px; background:#0b1220; border:1px solid #1f2937; border-radius: 10px; color:#e5e7eb; outline:none; }
    .auth-btn { margin-top:10px; width:100%; padding:10px 12px; border-radius:10px; border:1px solid #2563eb; background: linear-gradient(90deg,#1d4ed8,#2563eb,#1d4ed8); color:#e5e7eb; cursor:pointer; }
    .auth-err { color:#f87171; font-size: 12px; min-height: 16px; margin-top:6px; }
  </style>
  <script>
    const AUTH_HASH = "__AUTH_HASH__";
    async function sha256(message) {
      const msgBuffer = new TextEncoder().encode(message);
      const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    }
    function showAuth() {
      const mask = document.getElementById('auth-mask');
      const input = document.getElementById('auth-input');
      const err = document.getElementById('auth-err');
      const btn = document.getElementById('auth-btn');
      mask.style.display = 'flex';
      input.focus();
      async function submit() {
        const pwd = input.value || '';
        const h = await sha256(pwd);
        if (h.toLowerCase() === AUTH_HASH.toLowerCase()) {
          mask.style.display = 'none';
          document.documentElement.style.display = '';
        } else {
          err.textContent = '密码错误，请重试';
        }
      }
      btn.addEventListener('click', submit);
      input.addEventListener('keydown', (e)=>{ if(e.key==='Enter'){ submit(); }});
    }
    function gate() {
      if (!AUTH_HASH) { document.documentElement.style.display = ''; return; }
      // 优先读取本地令牌
      try{
        const tk = localStorage.getItem('gauth');
        if(tk && tk.toLowerCase() === AUTH_HASH.toLowerCase()){
          document.documentElement.style.display = '';
          return;
        }
      }catch(e){}
      // 无令牌则跳登录页
      location.replace('login.html');
    }
    document.documentElement.style.display = 'none';
    document.addEventListener('DOMContentLoaded', gate);
    // 根据是否有配额数据隐藏卡片
    document.addEventListener('DOMContentLoaded', ()=>{
      const qleft = '__QLEFT__'; const qcap = '__QCAP__'; const kok='__KOK__'; const kt='__KTOTAL__';
      const hideQuota = (!qleft || qleft==='0') && (!qcap || qcap==='0') && (!kok || kok==='0') && (!kt || kt==='0');
      if(hideQuota){
        document.querySelectorAll('.stat.quota').forEach(el=>el.style.display='none');
      }
    });
  </script>
</head>
<body>
  <div class="wrap">
    <div id="auth-mask" class="auth-mask" style="display:none">
      <div class="auth-card">
        <h3 class="auth-title">访问认证</h3>
        <p class="auth-sub">请输入访问密码以查看页面内容</p>
        <input id="auth-input" class="auth-input" type="password" placeholder="输入密码" />
        <button id="auth-btn" class="auth-btn">进入</button>
        <div id="auth-err" class="auth-err"></div>
      </div>
    </div>
    <div class="header">
      <h1>Google SSR Actions</h1>
      <small>构建时间(中国时区)：__TS_CN__</small>
    </div>
    <div class="subtitle">源 __ALIVE__/__TOTAL__ · 节点 __NODES__ · 新增 __NEW__ · 移除 __REMOVED__</div>

    <div class="stats" id="stats-cards">
      <div class="stat quota" data-hide="q"><div class="num">__QLEFT__</div><div>剩余额度</div></div>
      <div class="stat quota" data-hide="q"><div class="num">__QCAP__</div><div>总额度</div></div>
      <div class="stat quota" data-hide="q"><div class="num">__KOK__/__KTOTAL__</div><div>可用密钥/总密钥</div></div>
      <div class="stat"><div class="num">__NEXT_CN__</div><div>下次更新时间(中国时区)</div></div>
    </div>

    <div class="grid">
      <div class="card">
        <h3>关键指标（7/30天）</h3>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px">
          <div>
            <small>新增(7天)</small>
            <canvas id="spark-added-7" height="40"></canvas>
          </div>
          <div>
            <small>失效(7天)</small>
            <canvas id="spark-removed-7" height="40"></canvas>
          </div>
          <div>
            <small>存活(30天)</small>
            <canvas id="spark-alive-30" height="40"></canvas>
          </div>
        </div>
      </div>
      <div class="card">
        <h3>订阅文件</h3>
        <ul>
          <li><a href="sub/all.txt"><code>sub/all.txt</code></a> 全量订阅</li>
          <li><a href="sub/all.yaml"><code>sub/all.yaml</code></a> Clash配置</li>
        </ul>
      </div>

      <div class="card">
        <h3>URL 源</h3>
        <ul>
          <li><a href="sub/urls.txt"><code>urls.txt</code></a> 当前可用源</li>
          <li><a href="sub/all_urls.txt"><code>all_urls.txt</code></a> 完整源列表</li>
          <li><a href="sub/google_urls.txt"><code>google_urls.txt</code></a> Google发现（__GCOUNT__）</li>
          <li><a href="sub/github_urls.txt"><code>github_urls.txt</code></a> GitHub发现（__GHCOUNT__）</li>
        </ul>
      </div>

      <div class="card">
        <h3>协议分布</h3>
        <ul>
          <li>SS：__SS__</li>
          <li>VMess：__VMESS__</li>
          <li>VLESS：__VLESS__</li>
          <li>Trojan：__TROJAN__</li>
          <li>Hysteria2：__HY2__</li>
        </ul>
      </div>

      <div class="card">
        <h3>辅助输出</h3>
        <ul>
          <li><a href="sub/github.txt"><code>github.txt</code></a> GitHub节点</li>
          <li><a href="sub/proto/ss-base64.txt"><code>ss-base64.txt</code></a> SS Base64</li>
          <li><a href="health.json"><code>health.json</code></a> 健康信息</li>
        </ul>
      </div>

      <div class="card card-wide">
        <h3>源详细信息</h3>
        <p><small>包含机场名称、容量/剩余、协议、复制与测速、详情页。</small></p>
        <div id="url-meta"><small>加载中...</small></div>
        <div class="chart">
          <h4 style="margin:0 0 8px 0">每日新增可用URL</h4>
          <canvas id="dailyChart" height="120"></canvas>
        </div>
        <script>
          function copyText(text){
            navigator.clipboard.writeText(text).then(()=>{
              alert('已复制订阅链接');
            }).catch(()=>{});
          }
          async function testSpeed(url){
            const t0 = performance.now();
            try{ await fetch(url, {method:'HEAD', mode:'no-cors'}); }catch(e){}
            const t1 = performance.now();
            return Math.round(t1 - t0);
          }
          async function runBatchSpeed(urls, concurrency){
            const results = new Array(urls.length).fill(null);
            let idx = 0;
            async function worker(){
              while(idx < urls.length){
                const i = idx++;
                const u = urls[i];
                const ms = await testSpeed(u);
                results[i] = ms;
                const cell = document.querySelector(`[data-url-id="${i}"]`);
                if(cell){
                  cell.textContent = ms;
                  cell.style.color = ms<=300?'#10b981':(ms<=800?'#60a5fa':'#f59e0b');
                }
              }
            }
            const workers = Array.from({length: Math.min(concurrency, urls.length)}, ()=>worker());
            await Promise.all(workers.map(w=>w()));
            return results;
          }
          async function loadMeta() {
            try {
              const res = await fetch('sub/url_meta.json', { cache: 'no-cache' });
              if (!res.ok) throw new Error('fetch failed');
              let data = await res.json();
              // 只展示可用源
              data = (Array.isArray(data) ? data : []).filter(x=>x && x.available);
              const rows = data.map(function(item, i){
                const q = (item.quality_score ?? 0);
                const qColor = q>=80?'#10b981':(q>=60?'#60a5fa':'#f59e0b');
                const src = (item.source||'').toLowerCase();
                const pillColor = src==='github'?'#111827': '#0b1220';
                const pillText = src==='github'?'GitHub':'Google';
                return '<tr>' +
                  '<td><div style="display:flex;gap:8px;align-items:center">' +
                    '<a href="' + (item.url||'#') + '" target="_blank">源</a>' +
                    '<small style="color:#94a3b8">' + (item.provider||item.host||'') + '</small>' +
                  '</div></td>' +
                  '<td>' + (item.available ? '✅' : '❌') + '</td>' +
                  '<td>' + (item.nodes_total ?? 0) + '</td>' +
                  '<td>' + (item.protocols ?? '') + '</td>' +
                  '<td>' + ((item.traffic?.remaining ?? '-') + ' / ' + (item.traffic?.total ?? '-') + ' ' + (item.traffic?.unit ?? '')) + '</td>' +
                  '<td data-url-id="' + i + '">' + (item.response_ms ?? '-') + '</td>' +
                  '<td><b style="color:' + qColor + '">' + q + '</b></td>' +
                  '<td><span class="pill" style="background:' + pillColor + '">' + pillText + '</span></td>' +
                  '<td>' + (item.first_seen || '-') + '</td>' +
                  '<td>' +
                    '<button onclick="copyText(\'' + (item.url||'') + '\')" style="padding:4px 8px;border-radius:8px;border:1px solid #1f2937;background:#0b1220;color:#e5e7eb">复制</button>' +
                    '<button class="btn-speed" data-url="' + (item.url||'') + '" style="margin-left:6px;padding:4px 8px;border-radius:8px;border:1px solid #1f2937;background:#0b1220;color:#e5e7eb">测速</button>' +
                    (item.detail_page ? '<a href="' + item.detail_page + '" style="margin-left:8px">详情</a>' : '') +
                  '</td>' +
                '</tr>';
              }).join('');
              const html = '<table>' +
                '<thead><tr>' +
                '<th style="text-align:left">URL/机场</th>' +
                '<th>可用</th>' +
                '<th>节点数</th>' +
                '<th>协议</th>' +
                '<th>流量(剩余/总量)</th>' +
                '<th>耗时(ms)</th>' +
                '<th>质量</th>' +
                '<th>来源</th>' +
                '<th>采集</th>' +
                '<th>操作</th>' +
                '</tr></thead>' +
                '<tbody>' + rows + '</tbody>' +
                '</table>';
              document.getElementById('url-meta').innerHTML = html;
              // 绑定单击测速
              document.querySelectorAll('.btn-speed').forEach(btn=>{
                btn.addEventListener('click', async (e)=>{
                  const u = e.currentTarget.getAttribute('data-url');
                  const ms = await testSpeed(u);
                  e.currentTarget.closest('tr').querySelector('[data-url-id]').textContent = ms;
                });
              });
              // 批量测速（限并发 6）
              const urls = data.map(x=>x.url);
              runBatchSpeed(urls, 6);
            } catch(e) {
              document.getElementById('url-meta').innerHTML = '<small>未获取到源详情</small>';
            }
          }
          async function loadDailyChart() {
            try {
              const r = await fetch('sub/stats_daily.json', { cache:'no-cache' });
              if (!r.ok) return;
              const d = await r.json();
              const labels = d.map(x=>x.date);
              const google = d.map(x=>x.google_added||0);
              const github = d.map(x=>x.github_added||0);
              const added = d.map(x=>x.new_total||0);
              const removed = d.map(x=>x.removed_total||0);
              const canvas = document.getElementById('dailyChart');
              const ctx = canvas.getContext('2d');
              // 极简绘制
              const max = Math.max(1, ...google, ...github, ...added, ...removed);
              const W = canvas.width = canvas.clientWidth;
              const H = canvas.height;
              function plot(series, color, yoff) {
                ctx.strokeStyle=color; ctx.lineWidth=2; ctx.beginPath();
                series.forEach((v,i)=>{
                  const x = (W-20) * (i/(series.length-1)) + 10;
                  const y = H-10 - (H-20) * (v/max);
                  if (i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
                }); ctx.stroke();
              }
              ctx.clearRect(0,0,W,H); ctx.fillStyle='#0b1220'; ctx.fillRect(0,0,W,H);
              plot(google,'#60a5fa'); plot(github,'#10b981'); plot(added,'#a78bfa'); plot(removed,'#f87171');
            } catch(e) {}
          }
          function drawSparkline(canvasId, series, color){
            const c = document.getElementById(canvasId); if(!c) return; const ctx=c.getContext('2d');
            const W = c.width = c.clientWidth || 160; const H = c.height; const max = Math.max(1, ...series);
            ctx.clearRect(0,0,W,H); ctx.strokeStyle=color; ctx.lineWidth=2; ctx.beginPath();
            series.forEach((v,i)=>{ const x=(W-6)*(i/(series.length-1))+3; const y=H-3 - (H-6)*(v/max); if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y); });
            ctx.stroke();
          }
          async function loadSparklines(){
            try{
              const r = await fetch('sub/stats_daily.json', { cache:'no-cache' }); if(!r.ok) return;
              const d = await r.json();
              const last7 = d.slice(-7);
              const last30 = d.slice(-30);
              drawSparkline('spark-added-7', last7.map(x=>x.new_total||0), '#60a5fa');
              drawSparkline('spark-removed-7', last7.map(x=>x.removed_total||0), '#f87171');
              drawSparkline('spark-alive-30', last30.map(x=>x.alive_total||0), '#10b981');
            }catch(e){}
          }
          loadMeta(); loadDailyChart(); loadSparklines();
        </script>
      </div>
    </div>

    <p><small>仅展示可用源（自动过滤失效/超额/限速来源）。 构建(UTC)：__TS__ · 下次(UTC)：__NEXT__</small></p>
  </div>
</body>
</html>

