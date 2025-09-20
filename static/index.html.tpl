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
    .card h3 { margin: 0 0 12px; font-size: 17px; color:#fff; border-left:3px solid var(--accent); padding-left:10px; }
    code { background:#0b1220; padding: 2px 6px; border-radius: 6px; border: 1px solid #1f2937; color:#d1d5db; }
    small { color: var(--muted); }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
    table { color:#e5e7eb; }
    th,td { padding:8px 10px; border-bottom:1px solid #1f2937; }
    th { color:#cbd5e1; text-align:left; background:#0b1220; position:sticky; top:0; }
    .ok { color: var(--ok); }
    .bad { color: var(--bad); }
    .chart { background: var(--panel); border:1px solid #1f2937; border-radius:12px; padding:12px; margin-top:16px; }
  </style>
  <script>
    const AUTH_HASH = "__AUTH_HASH__";
    async function sha256(message) {
      const msgBuffer = new TextEncoder().encode(message);
      const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    }
    async function gate() {
      if (!AUTH_HASH) { document.documentElement.style.display = ''; return; }
      let ok = false;
      for (let i = 0; i < 3; i++) {
        const pwd = window.prompt('请输入访问密码');
        if (pwd === null) break;
        const h = await sha256(pwd);
        if (h.toLowerCase() === AUTH_HASH.toLowerCase()) { ok = true; break; }
        alert('密码错误');
      }
      if (!ok) { document.body.innerHTML = '<p style="margin:24px;color:#ef4444">未授权访问</p>'; return; }
      document.documentElement.style.display = '';
    }
    document.documentElement.style.display = 'none';
    document.addEventListener('DOMContentLoaded', gate);
  </script>
</head>
<body>
  <div class="wrap">
    <div class="header">
      <h1>Google SSR Actions</h1>
      <small>构建时间(中国时区)：__TS_CN__</small>
    </div>
    <div class="subtitle">源 __ALIVE__/__TOTAL__ · 节点 __NODES__ · 新增 __NEW__ · 移除 __REMOVED__</div>

    <div class="stats">
      <div class="stat"><div class="num">__QLEFT__</div><div>剩余额度</div></div>
      <div class="stat"><div class="num">__QCAP__</div><div>总额度</div></div>
      <div class="stat"><div class="num">__KOK__/__KTOTAL__</div><div>可用密钥/总密钥</div></div>
      <div class="stat"><div class="num">__NEXT_CN__</div><div>下次更新时间(中国时区)</div></div>
    </div>

    <div class="grid">
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
            try{
              const r = await fetch(url, {method:'HEAD', mode:'no-cors'});
            }catch(e){}
            const t1 = performance.now();
            alert('粗略测速: ' + Math.round(t1 - t0) + ' ms');
          }
          async function loadMeta() {
            try {
              const res = await fetch('sub/url_meta.json', { cache: 'no-cache' });
              if (!res.ok) throw new Error('fetch failed');
              const data = await res.json();
              const rows = data.map(function(item){
                return '<tr>' +
                  '<td><div style="display:flex;gap:8px;align-items:center">' +
                    '<a href="' + (item.url||'#') + '" target="_blank">源</a>' +
                    '<small style="color:#94a3b8">' + (item.provider||item.host||'') + '</small>' +
                  '</div></td>' +
                  '<td>' + (item.available ? '✅' : '❌') + '</td>' +
                  '<td>' + (item.nodes_total ?? 0) + '</td>' +
                  '<td>' + (item.protocols ?? '') + '</td>' +
                  '<td>' + ((item.traffic?.remaining ?? '-') + ' / ' + (item.traffic?.total ?? '-') + ' ' + (item.traffic?.unit ?? '')) + '</td>' +
                  '<td>' + (item.response_ms ?? '-') + '</td>' +
                  '<td>' +
                    '<button onclick="copyText(\'' + (item.url||'') + '\')" style="padding:4px 8px;border-radius:8px;border:1px solid #1f2937;background:#0b1220;color:#e5e7eb">复制</button>' +
                    '<button onclick="testSpeed(\'' + (item.url||'') + '\')" style="margin-left:6px;padding:4px 8px;border-radius:8px;border:1px solid #1f2937;background:#0b1220;color:#e5e7eb">测速</button>' +
                    (item.detail_page ? '<a href="' + item.detail_page + '" style="margin-left:6px">详情</a>' : '') +
                  '</td>' +
                '</tr>';
              }).join('');
              const html = '<table style="width:100%;border-collapse:collapse">' +
                '<thead><tr>' +
                '<th style="text-align:left">URL/机场</th>' +
                '<th>可用</th>' +
                '<th>节点数</th>' +
                '<th>协议</th>' +
                '<th>流量(剩余/总量)</th>' +
                '<th>耗时(ms)</th>' +
                '<th>操作</th>' +
                '</tr></thead>' +
                '<tbody>' + rows + '</tbody>' +
                '</table>';
              document.getElementById('url-meta').innerHTML = html;
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
              const canvas = document.getElementById('dailyChart');
              const ctx = canvas.getContext('2d');
              // 极简绘制
              const max = Math.max(1, ...google, ...github);
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
              plot(google,'#60a5fa'); plot(github,'#10b981');
            } catch(e) {}
          }
          loadMeta(); loadDailyChart();
        </script>
      </div>

      <div class="card">
        <h3>辅助输出</h3>
        <ul>
          <li><a href="sub/github.txt"><code>github.txt</code></a> GitHub节点</li>
          <li><a href="sub/proto/ss-base64.txt"><code>ss-base64.txt</code></a> SS Base64</li>
          <li><a href="health.json"><code>health.json</code></a> 健康信息</li>
        </ul>
      </div>
    </div>

    <p><small>仅展示可用源（自动过滤失效/超额/限速来源）。 构建(UTC)：__TS__ · 下次(UTC)：__NEXT__</small></p>
  </div>
</body>
</html>

