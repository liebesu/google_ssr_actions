<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Google SSR Actions - 订阅聚合</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 0; background: #f7fafc; }
    .wrap { max-width: 1080px; margin: 0 auto; padding: 28px; }
    .header { display:flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px; }
    .subtitle { color:#6b7280; margin-top: 4px; }
    .stats { display:grid; grid-template-columns: repeat(auto-fit, minmax(140px,1fr)); gap: 12px; margin: 16px 0 24px; }
    .stat { background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:14px; text-align:center; }
    .stat .num { font-size: 20px; font-weight: 700; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
    .card { background:#fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 16px; }
    .card h3 { margin: 0 0 10px; font-size: 16px; }
    code { background:#f3f4f6; padding: 2px 6px; border-radius: 4px; }
    small { color: #6b7280; }
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
        <p><small>以下为每个订阅URL的可用性、节点与流量概览（仅显示可用源）。</small></p>
        <div id="url-meta"><small>加载中...</small></div>
        <script>
          async function loadMeta() {
            try {
              const res = await fetch('sub/url_meta.json', { cache: 'no-cache' });
              if (!res.ok) throw new Error('fetch failed');
              const data = await res.json();
              const rows = data.map(function(item){
                return '<tr>' +
                  '<td><a href="' + (item.url||'#') + '" target="_blank">源</a></td>' +
                  '<td>' + (item.available ? '✅' : '❌') + '</td>' +
                  '<td>' + (item.nodes_total ?? 0) + '</td>' +
                  '<td>' + (item.protocols ?? '') + '</td>' +
                  '<td>' + ((item.traffic?.remaining ?? '-') + ' / ' + (item.traffic?.total ?? '-') + ' ' + (item.traffic?.unit ?? '')) + '</td>' +
                  '<td>' + (item.response_ms ?? '-') + '</td>' +
                '</tr>';
              }).join('');
              const html = '<table style="width:100%;border-collapse:collapse">' +
                '<thead><tr>' +
                '<th style="text-align:left">URL</th>' +
                '<th>可用</th>' +
                '<th>节点数</th>' +
                '<th>协议</th>' +
                '<th>流量(剩余/总量)</th>' +
                '<th>耗时(ms)</th>' +
                '</tr></thead>' +
                '<tbody>' + rows + '</tbody>' +
                '</table>';
              document.getElementById('url-meta').innerHTML = html;
            } catch(e) {
              document.getElementById('url-meta').innerHTML = '<small>未获取到源详情</small>';
            }
          }
          loadMeta();
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

