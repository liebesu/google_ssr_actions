<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Google SSR Actions - 订阅聚合</title>
  <link rel="stylesheet" href="styles.css" />
  <script>
    const AUTH_HASH = "__AUTH_HASH__";
    const AUTH_USER = "__AUTH_USER__";
    async function sha256(message) {
      const msgBuffer = new TextEncoder().encode(message);
      const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    }
    function showAuth() {
      const mask = document.getElementById('auth-mask');
      const userInput = document.getElementById('auth-user');
      const passInput = document.getElementById('auth-input');
      const err = document.getElementById('auth-err');
      const btn = document.getElementById('auth-btn');
      mask.style.display = 'flex';
      userInput.focus();
      async function submit() {
        const user = userInput.value.trim();
        const pwd = passInput.value || '';
        const h = await sha256(pwd);
        const userRequired = (AUTH_USER || '').trim().length > 0;
        const userOk = userRequired ? (user === (AUTH_USER||'').trim()) : true;
        if (userOk && h.toLowerCase() === AUTH_HASH.toLowerCase()) {
          console.log('🎉 认证成功！');
          try{ 
            localStorage.setItem('gauth', h); 
            localStorage.setItem('guser', user); 
            console.log('✅ 认证信息已保存到localStorage');
          }catch(e){
            console.error('保存认证信息失败:', e);
          }
          mask.style.display = 'none';
          document.documentElement.style.display = '';
          console.log('✅ 页面已显示，开始加载内容...');
          
          // 手动触发页面内容加载
          setTimeout(() => {
            try {
              if (typeof loadMeta === 'function') loadMeta();
              if (typeof loadDailyChart === 'function') loadDailyChart();
              if (typeof loadSparklines === 'function') loadSparklines();
              if (typeof loadSerpAPIKeys === 'function') loadSerpAPIKeys();
              if (typeof loadRecentUrls === 'function') loadRecentUrls();
              console.log('✅ 所有内容加载函数已触发');
            } catch(e) {
              console.error('内容加载出错:', e);
            }
          }, 100);
        } else {
          console.log('❌ 认证失败');
          err.textContent = '用户名或密码错误，请重试';
        }
      }
      btn.addEventListener('click', submit);
      passInput.addEventListener('keydown', (e)=>{ if(e.key==='Enter'){ submit(); }});
    }
    function gate() {
      console.log('🔐 认证检查开始...');
      console.log('AUTH_HASH:', AUTH_HASH ? '已设置' : '未设置');
      console.log('AUTH_USER:', AUTH_USER ? '已设置' : '未设置');
      
      if (!AUTH_HASH || AUTH_HASH.trim() === '') { 
        console.log('✅ 无需认证，直接显示页面');
        document.documentElement.style.display = ''; 
        return; 
      }
      
      try{
        const tk = localStorage.getItem('gauth');
        const gu = (localStorage.getItem('guser') || '').trim();
        const userRequired = (AUTH_USER || '').trim().length > 0;
        const passOk = !!tk && (tk.toLowerCase() === AUTH_HASH.toLowerCase());
        const userOk = userRequired ? (gu === (AUTH_USER||'').trim()) : true;
        
        console.log('存储的认证:', tk ? '存在' : '不存在');
        console.log('密码验证:', passOk ? '通过' : '失败');
        console.log('用户验证:', userOk ? '通过' : '失败');
        
        if (passOk && userOk) { 
          console.log('✅ 认证成功，显示页面');
          document.documentElement.style.display = ''; 
          
          // 确保内容加载函数在页面显示后执行
          setTimeout(() => {
            try {
              if (typeof loadMeta === 'function') loadMeta();
              if (typeof loadDailyChart === 'function') loadDailyChart();
              if (typeof loadSparklines === 'function') loadSparklines();
              if (typeof loadSerpAPIKeys === 'function') loadSerpAPIKeys();
              if (typeof loadRecentUrls === 'function') loadRecentUrls();
              console.log('✅ 自动加载所有内容完成');
            } catch(e) {
              console.error('自动内容加载出错:', e);
            }
          }, 100);
          return;
        }
      }catch(e){
        console.error('认证检查出错:', e);
      }
      
      console.log('❌ 认证失败，显示登录框');
      showAuth(); // 直接显示认证弹窗而不是跳转
    }
    // 强制确保页面能够显示
    console.log('🚀 页面初始化开始...');
    
    // 先立即显示页面，然后进行认证检查
    document.documentElement.style.display = '';
    
    // 延迟隐藏页面，给认证检查足够时间
    setTimeout(function() {
      console.log('🔐 开始认证检查，暂时隐藏页面...');
      document.documentElement.style.display = 'none';
      
      // 立即进行认证检查
      gate();
      
      // 超短时间fallback - 确保用户能看到内容
      setTimeout(function() {
        if (document.documentElement.style.display === 'none') {
          console.log('⚠️ 1秒fallback - 强制显示认证框');
          showAuth();
        }
      }, 1000);
      
      // 最终fallback - 无论如何都要显示
      setTimeout(function() {
        if (document.documentElement.style.display === 'none') {
          console.log('🚨 最终fallback - 强制显示页面');
          document.documentElement.style.display = '';
          showAuth();
        }
      }, 2000);
      
    }, 100);
    
    // 多重事件监听保障
    document.addEventListener('DOMContentLoaded', function() {
      console.log('📄 DOM加载完成，检查认证状态...');
      setTimeout(gate, 50);
    });
    
    window.addEventListener('load', function() {
      console.log('🌐 页面完全加载，最终检查...');
      setTimeout(function() {
        if (document.documentElement.style.display === 'none') {
          console.log('⚠️ 页面加载完成但仍隐藏，强制显示认证框');
          showAuth();
        }
      }, 100);
    });
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
        <p class="auth-sub">请输入用户名和密码以查看页面内容</p>
        <input id="auth-user" class="auth-input" type="text" placeholder="输入用户名" />
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
      <!-- 重要卡片优先显示 -->
      <div class="card card-files">
        <h3>🔗 订阅文件</h3>
        <div class="file-list">
          <div class="file-item">
            <div class="file-info">
              <div class="file-name">
                <a href="sub/all.txt"><code>all.txt</code></a>
                <span class="file-desc">全量订阅 (文本格式)</span>
              </div>
              <div class="file-stats">
                <span class="nodes-count">__NODES__ 节点</span>
              </div>
            </div>
            <button onclick="copyFileUrl('sub/all.txt', this)" class="copy-btn">
              <span class="copy-icon">📋</span>
              <span class="copy-text">复制链接</span>
            </button>
          </div>
          <div class="file-item">
            <div class="file-info">
              <div class="file-name">
                <a href="sub/all.yaml"><code>all.yaml</code></a>
                <span class="file-desc">Clash配置 (完整节点)</span>
              </div>
              <div class="file-stats">
                <span class="file-type">YAML</span>
              </div>
            </div>
            <button onclick="copyFileUrl('sub/all.yaml', this)" class="copy-btn">
              <span class="copy-icon">📋</span>
              <span class="copy-text">复制链接</span>
            </button>
          </div>
          <div class="file-item">
            <div class="file-info">
              <div class="file-name">
                <a href="sub/all_providers.yaml"><code>all_providers.yaml</code></a>
                <span class="file-desc">Clash配置 (代理提供商)</span>
              </div>
              <div class="file-stats">
                <span class="file-type">YAML</span>
              </div>
            </div>
            <button onclick="copyFileUrl('sub/all_providers.yaml', this)" class="copy-btn">
              <span class="copy-icon">📋</span>
              <span class="copy-text">复制链接</span>
            </button>
          </div>
        </div>
        <p class="card-note">📌 所有订阅文件和接口可直接访问，无需页面认证</p>
      </div>

      <!-- URL源文件卡片 -->
      <div class="card card-sources">
        <h3>📂 URL源文件</h3>
        <div class="file-list">
          <div class="file-item">
            <div class="file-info">
              <div class="file-name">
                <a href="sub/urls.txt"><code>urls.txt</code></a>
                <span class="file-desc">当前可用源</span>
              </div>
              <div class="file-stats">
                <span class="status-badge available">✅ 已验证</span>
              </div>
            </div>
            <button onclick="copyFileUrl('sub/urls.txt', this)" class="copy-btn">
              <span class="copy-icon">📋</span>
              <span class="copy-text">复制</span>
            </button>
          </div>
          <div class="file-item">
            <div class="file-info">
              <div class="file-name">
                <a href="sub/all_urls.txt"><code>all_urls.txt</code></a>
                <span class="file-desc">完整源列表</span>
              </div>
              <div class="file-stats">
                <span class="status-badge complete">📋 完整</span>
              </div>
            </div>
            <button onclick="copyFileUrl('sub/all_urls.txt', this)" class="copy-btn">
              <span class="copy-icon">📋</span>
              <span class="copy-text">复制</span>
            </button>
          </div>
          <div class="file-item">
            <div class="file-info">
              <div class="file-name">
                <a href="sub/google_urls.txt"><code>google_urls.txt</code></a>
                <span class="file-desc">Google发现</span>
              </div>
              <div class="file-stats">
                <span class="count-badge">__GCOUNT__ 个</span>
              </div>
            </div>
            <button onclick="copyFileUrl('sub/google_urls.txt', this)" class="copy-btn">
              <span class="copy-icon">📋</span>
              <span class="copy-text">复制</span>
            </button>
          </div>
          <div class="file-item">
            <div class="file-info">
              <div class="file-name">
                <a href="sub/github_urls.txt"><code>github_urls.txt</code></a>
                <span class="file-desc">GitHub发现</span>
              </div>
              <div class="file-stats">
                <span class="count-badge">__GHCOUNT__ 个</span>
              </div>
            </div>
            <button onclick="copyFileUrl('sub/github_urls.txt', this)" class="copy-btn">
              <span class="copy-icon">📋</span>
              <span class="copy-text">复制</span>
            </button>
          </div>
        </div>
      </div>

      <!-- 辅助输出卡片 -->
      <div class="card card-extras">
        <h3>🛠️ 辅助输出</h3>
        <div class="file-list">
          <div class="file-item">
            <div class="file-info">
              <div class="file-name">
                <a href="sub/github.txt"><code>github.txt</code></a>
                <span class="file-desc">GitHub节点</span>
              </div>
              <div class="file-stats">
                <span class="file-type">TXT</span>
              </div>
            </div>
            <button onclick="copyFileUrl('sub/github.txt', this)" class="copy-btn">
              <span class="copy-icon">📋</span>
              <span class="copy-text">复制</span>
            </button>
          </div>
          <div class="file-item">
            <div class="file-info">
              <div class="file-name">
                <a href="sub/proto/ss-base64.txt"><code>ss-base64.txt</code></a>
                <span class="file-desc">SS Base64编码</span>
              </div>
              <div class="file-stats">
                <span class="file-type">Base64</span>
              </div>
            </div>
            <button onclick="copyFileUrl('sub/proto/ss-base64.txt', this)" class="copy-btn">
              <span class="copy-icon">📋</span>
              <span class="copy-text">复制</span>
            </button>
          </div>
          <div class="file-item">
            <div class="file-info">
              <div class="file-name">
                <a href="health.json"><code>health.json</code></a>
                <span class="file-desc">健康状态API</span>
              </div>
              <div class="file-stats">
                <span class="file-type">JSON</span>
              </div>
            </div>
            <button onclick="copyFileUrl('health.json', this)" class="copy-btn">
              <span class="copy-icon">📋</span>
              <span class="copy-text">复制</span>
            </button>
          </div>
        </div>
        <p class="card-note">💡 API接口和JSON数据可通过程序直接调用</p>
      </div>

      <!-- 其他卡片 -->
      <div class="card card-metrics">
        <h3>📊 关键指标趋势</h3>
        <div class="metrics-grid">
          <div class="metric-item">
            <div class="metric-header">
              <span class="metric-label">📈 新增源 (7天)</span>
              <span class="metric-value" id="new-count-7">-</span>
            </div>
            <canvas id="spark-added-7" height="40"></canvas>
          </div>
          <div class="metric-item">
            <div class="metric-header">
              <span class="metric-label">📉 失效源 (7天)</span>
              <span class="metric-value" id="removed-count-7">-</span>
            </div>
            <canvas id="spark-removed-7" height="40"></canvas>
          </div>
          <div class="metric-item">
            <div class="metric-header">
              <span class="metric-label">💚 存活源 (30天)</span>
              <span class="metric-value" id="alive-count-30">-</span>
            </div>
            <canvas id="spark-alive-30" height="40"></canvas>
          </div>
        </div>
        
        <!-- 7天趋势详情图表 -->
        <div class="trend-details">
          <h4>📈 前七天详细趋势</h4>
          <div class="trend-chart-container">
            <canvas id="trend7day-chart" width="400" height="200"></canvas>
          </div>
          <div class="trend-legend">
            <div class="legend-item">
              <span class="legend-color" style="background: #10b981;"></span>
              <span class="legend-label">新增源</span>
            </div>
            <div class="legend-item">
              <span class="legend-color" style="background: #ef4444;"></span>
              <span class="legend-label">失效源</span>
            </div>
            <div class="legend-item">
              <span class="legend-color" style="background: #22c55e;"></span>
              <span class="legend-label">存活源</span>
            </div>
            <div class="legend-item">
              <span class="legend-color" style="background: #f59e0b;"></span>
              <span class="legend-label">净增长</span>
            </div>
          </div>
        </div>
      </div>

      <div class="card card-recent">
        <h3>🆕 最新有效订阅源</h3>
        <div id="recent-urls">
          <div class="loading-placeholder">正在加载最新源...</div>
        </div>
      </div>

      <div class="card card-health">
        <h3>健康信息</h3>
        <ul class="health-list">
          <li>构建时间(中国时区)：<b>__TS_CN__</b></li>
          <li>下次更新时间(中国时区)：<b>__NEXT_CN__</b></li>
          <li>源：<b>__ALIVE__/__TOTAL__</b> · 新增 <b>__NEW__</b> · 移除 <b>__REMOVED__</b></li>
          <li>节点：<b>__NODES__</b> · 协议 SS <b>__SS__</b> | VMess <b>__VMESS__</b> | VLESS <b>__VLESS__</b> | Trojan <b>__TROJAN__</b> | HY2 <b>__HY2__</b></li>
          <li>来源：Google <b>__GCOUNT__</b> | GitHub <b>__GHCOUNT__</b></li>
        </ul>
      </div>

      <div class="card card-serpapi">
        <h3>SerpAPI 密钥状态</h3>
        <div id="serpapi-status">
          <div class="serpapi-summary">
            <span class="status-item">可用密钥: <b id="keys-ok">__KOK__</b>/<b id="keys-total">__KTOTAL__</b></span>
            <span class="status-item">总剩余额度: <b id="quota-left">__QLEFT__</b>/<b id="quota-cap">__QCAP__</b></span>
          </div>
          <div id="serpapi-keys-list" class="serpapi-keys-list">
            <!-- 动态加载密钥详情 -->
          </div>
        </div>
      </div>

      <div class="card card-protocols">
        <h3>协议分布</h3>
        <ul>
          <li>SS：__SS__</li>
          <li>VMess：__VMESS__</li>
          <li>VLESS：__VLESS__</li>
          <li>Trojan：__TROJAN__</li>
          <li>Hysteria2：__HY2__</li>
        </ul>
      </div>

      <div class="card card-wide card-details">
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
          function copyFileUrl(path, btn){
            const fullUrl = window.location.origin + window.location.pathname.replace(/\/[^\/]*$/, '/') + path;
            navigator.clipboard.writeText(fullUrl).then(()=>{
              // 临时改变按钮文本和样式
              const originalText = btn.textContent;
              btn.textContent = '✓ 已复制';
              btn.style.background = '#10b981';
              btn.style.borderColor = '#10b981';
              btn.style.color = 'white';
              
              setTimeout(() => {
                btn.textContent = originalText;
                btn.style.background = '#1f2937';
                btn.style.borderColor = '#374151';
                btn.style.color = '#9ca3af';
              }, 1500);
            }).catch(()=>{
              alert('复制失败，请手动复制: ' + fullUrl);
            });
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
              // 按质量分倒序排序
              data.sort((a,b)=> (b.quality_score||0) - (a.quality_score||0));
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
              
              // 更新指标数值
              const newCount7 = last7.reduce((sum, x) => sum + (x.new_total||0), 0);
              const removedCount7 = last7.reduce((sum, x) => sum + (x.removed_total||0), 0);
              const aliveCount30 = last30.length > 0 ? last30[last30.length-1].alive_total||0 : 0;
              
              document.getElementById('new-count-7').textContent = newCount7;
              document.getElementById('removed-count-7').textContent = removedCount7;
              document.getElementById('alive-count-30').textContent = aliveCount30;
              
              drawSparkline('spark-added-7', last7.map(x=>x.new_total||0), '#60a5fa');
              drawSparkline('spark-removed-7', last7.map(x=>x.removed_total||0), '#f87171');
              drawSparkline('spark-alive-30', last30.map(x=>x.alive_total||0), '#10b981');
            }catch(e){}
          }

          // 加载最新有效URL
          async function loadRecentUrls() {
            try {
              const res = await fetch('sub/url_meta.json', { cache: 'no-cache' });
              if (!res.ok) throw new Error('fetch failed');
              let data = await res.json();
              
              // 筛选最新的有效源
              data = (Array.isArray(data) ? data : []).filter(x=>x && x.available);
              
              // 按质量分和日期排序，取前5个
              data.sort((a,b)=> {
                const scoreA = (b.quality_score||0) - (a.quality_score||0);
                if (scoreA !== 0) return scoreA;
                return new Date(b.first_seen||'1970-01-01') - new Date(a.first_seen||'1970-01-01');
              });
              
              const recentData = data.slice(0, 5);
              const container = document.getElementById('recent-urls');
              
              if (recentData.length === 0) {
                container.innerHTML = '<div class="no-data">暂无最新源</div>';
                return;
              }
              
              container.innerHTML = recentData.map(item => {
                const host = item.host || new URL(item.url).hostname;
                const traffic = item.traffic || {};
                const remaining = traffic.remaining || '-';
                const total = traffic.total || '-';
                const unit = traffic.unit || '';
                const quality = item.quality_score || 0;
                const qualityColor = quality >= 80 ? '#10b981' : quality >= 60 ? '#60a5fa' : '#f59e0b';
                
                return `
                  <div class="recent-url-item">
                    <div class="url-header">
                      <div class="url-title">
                        <a href="${item.url}" target="_blank" class="url-link">${host}</a>
                        <span class="quality-score" style="color: ${qualityColor}">质量: ${quality}</span>
                      </div>
                      <div class="url-actions">
                        <button onclick="copyText('${item.url}')" class="copy-btn-mini">复制链接</button>
                      </div>
                    </div>
                    <div class="url-stats">
                      <span class="stat-item">📊 ${item.nodes_total || 0} 节点</span>
                      <span class="stat-item">💾 ${remaining}/${total} ${unit}</span>
                      <span class="stat-item">📅 ${item.first_seen || '-'}</span>
                    </div>
                  </div>
                `;
              }).join('');
              
            } catch(e) {
              document.getElementById('recent-urls').innerHTML = '<div class="error-msg">加载失败</div>';
            }
          }

          // 加载 SerpAPI 密钥详情
          async function loadSerpAPIKeys() {
            try {
              const r = await fetch('health.json', { cache:'no-cache' });
              if(!r.ok) return;
              const health = await r.json();
              const keys = health.serpapi_keys_detail || [];
              const container = document.getElementById('serpapi-keys-list');
              if(!container) return;
              
              if(keys.length === 0) {
                container.innerHTML = '<div class="serpapi-key-item error">暂无密钥信息</div>';
                return;
              }
              
              container.innerHTML = keys.map(key => {
                if(key.error) {
                  const keyInfo = key.key_masked ? `(${key.key_masked})` : '';
                  return `<div class="serpapi-key-item error">
                    <div class="key-header">
                      <span class="key-index">Key ${key.index} ${keyInfo}</span>
                      <span class="key-status">错误</span>
                    </div>
                    <div class="key-details">
                      <div style="color:#ef4444">${key.error}</div>
                      ${key.status === 'key_valid_unchecked' ? '<div style="color:#10b981;margin-top:4px">✓ 密钥格式有效，但无法检查配额</div>' : ''}
                      ${key.status === 'key_invalid' ? '<div style="color:#ef4444;margin-top:4px">✗ 密钥格式无效</div>' : ''}
                    </div>
                  </div>`;
                }
                const used = key.used_searches || 0;
                const total = key.searches_per_month || 0;
                const left = key.total_searches_left || 0;
                const usagePercent = total > 0 ? Math.round((used / total) * 100) : 0;
                const statusClass = left <= 0 ? 'exhausted' : (usagePercent > 80 ? 'warning' : 'ok');
                const resetDate = key.reset_date ? new Date(key.reset_date).toLocaleDateString('zh-CN') : '未知';
                const keyInfo = key.key_masked ? `(${key.key_masked})` : '';
                
                return `
                  <div class="serpapi-key-item ${statusClass}">
                    <div class="key-header">
                      <span class="key-index">Key ${key.index} ${keyInfo}</span>
                      <span class="key-status">${left <= 0 ? '已用尽' : (usagePercent > 80 ? '即将用尽' : '正常')}</span>
                    </div>
                    <div class="key-details">
                      <div class="quota-bar">
                        <div class="quota-fill" style="width: ${usagePercent}%"></div>
                      </div>
                      <div class="quota-text">已用 ${used}/${total} (${usagePercent}%) · 剩余 ${left}</div>
                      <div class="reset-info">重置时间: ${resetDate}</div>
                    </div>
                  </div>
                `;
              }).join('');
            } catch(e) { 
              console.warn('SerpAPI keys load failed:', e);
              const container = document.getElementById('serpapi-keys-list');
              if(container) container.innerHTML = '<div class="serpapi-key-item error">加载失败</div>';
            }
          }
          
          async function loadTrend7Day() {
            try {
              const r = await fetch('sub/stats_7day_enhanced.json', { cache:'no-cache' });
              if (!r.ok) {
                document.getElementById('trend7day-chart').style.display = 'none';
                return;
              }
              const data = await r.json();
              
              if (!data || data.length === 0) {
                document.getElementById('trend7day-chart').style.display = 'none';
                return;
              }
              
              // 绘制7天趋势图表
              const canvas = document.getElementById('trend7day-chart');
              if (!canvas) return;
              
              const ctx = canvas.getContext('2d');
              const W = canvas.width = canvas.clientWidth || 400;
              const H = canvas.height = 200;
              
              // 准备数据
              const dates = data.map(d => d.date || '');
              const newAdded = data.map(d => d.new_added || 0);
              const failed = data.map(d => d.failed_count || 0);
              const alive = data.map(d => d.alive_count || 0);
              const netGrowth = data.map(d => d.net_growth || 0);
              
              // 计算最大值用于缩放
              const maxValue = Math.max(1, ...newAdded, ...failed, ...alive, ...netGrowth);
              
              // 清空画布
              ctx.clearRect(0, 0, W, H);
              ctx.fillStyle = '#0b1220';
              ctx.fillRect(0, 0, W, H);
              
              // 绘制网格线
              ctx.strokeStyle = '#334155';
              ctx.lineWidth = 1;
              for (let i = 0; i <= 4; i++) {
                const y = 20 + (H - 40) * (i / 4);
                ctx.beginPath();
                ctx.moveTo(40, y);
                ctx.lineTo(W - 20, y);
                ctx.stroke();
              }
              
              // 绘制数据线
              function drawLine(series, color, lineWidth = 2) {
                ctx.strokeStyle = color;
                ctx.lineWidth = lineWidth;
                ctx.beginPath();
                series.forEach((value, i) => {
                  const x = 40 + (W - 60) * (i / (series.length - 1));
                  const y = H - 20 - (H - 40) * (value / maxValue);
                  if (i === 0) {
                    ctx.moveTo(x, y);
                  } else {
                    ctx.lineTo(x, y);
                  }
                });
                ctx.stroke();
              }
              
              // 绘制各条趋势线
              drawLine(newAdded, '#10b981', 3);  // 新增源 - 绿色
              drawLine(failed, '#ef4444', 2);    // 失效源 - 红色
              drawLine(alive, '#22c55e', 2);     // 存活源 - 绿色
              drawLine(netGrowth, '#f59e0b', 2); // 净增长 - 橙色
              
              // 绘制数据点
              function drawPoints(series, color) {
                ctx.fillStyle = color;
                series.forEach((value, i) => {
                  const x = 40 + (W - 60) * (i / (series.length - 1));
                  const y = H - 20 - (H - 40) * (value / maxValue);
                  ctx.beginPath();
                  ctx.arc(x, y, 3, 0, 2 * Math.PI);
                  ctx.fill();
                });
              }
              
              drawPoints(newAdded, '#10b981');
              drawPoints(failed, '#ef4444');
              drawPoints(alive, '#22c55e');
              drawPoints(netGrowth, '#f59e0b');
              
              // 绘制X轴标签（日期）
              ctx.fillStyle = '#94a3b8';
              ctx.font = '11px ui-sans-serif';
              ctx.textAlign = 'center';
              dates.forEach((date, i) => {
                const x = 40 + (W - 60) * (i / (dates.length - 1));
                ctx.fillText(date, x, H - 5);
              });
              
              // 绘制Y轴标签
              ctx.textAlign = 'right';
              for (let i = 0; i <= 4; i++) {
                const value = Math.round(maxValue * (i / 4));
                const y = 20 + (H - 40) * (i / 4);
                ctx.fillText(value.toString(), 35, y + 4);
              }
              
            } catch(e) {
              console.warn('7天趋势图表加载失败:', e);
              const canvas = document.getElementById('trend7day-chart');
              if (canvas) canvas.style.display = 'none';
            }
          }
          
          loadMeta(); loadDailyChart(); loadSparklines(); loadSerpAPIKeys(); loadRecentUrls(); loadTrend7Day();
        </script>
      </div>
    </div>

    <p><small>仅展示可用源（自动过滤失效/超额/限速来源）。 构建(UTC)：__TS__ · 下次(UTC)：__NEXT__</small></p>
  </div>
</body>
</html>

