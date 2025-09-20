#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aggregator CLI for GitHub Actions

Responsibilities:
- Optionally run a one-shot scrape to discover new subscription URLs
- Merge with historical URLs and validate availability
- Download, decode and deduplicate nodes into a unified subscription (TXT)
- Produce protocol and region slices (TXT)
- Emit health.json and simple index.html
- Persist updated history/live URL lists under data/

Notes:
- YAML export is intentionally deferred for a second iteration to ensure
  correctness across multiple protocols; TXT outputs are Clash-compatible.
"""

import argparse
import base64
import json
import os
import re
import html as html_lib
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Set, Tuple

import requests
import yaml
import urllib3
from urllib3.exceptions import InsecureRequestWarning
from zoneinfo import ZoneInfo
import hashlib

# Suppress SSL warnings for verify=False requests
urllib3.disable_warnings(InsecureRequestWarning)

try:
    # Import for traffic extraction helpers without triggering notifications
    from subscription_checker import SubscriptionChecker  # type: ignore
except Exception:
    SubscriptionChecker = None  # type: ignore

# Ensure local imports resolve relative to this file
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = CURRENT_DIR
sys.path.append(PROJECT_ROOT)

from url_extractor import URLExtractor  # type: ignore
from github_search_scraper import discover_from_github  # type: ignore


def read_text_file_lines(path: str) -> List[str]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def read_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def safe_b64_decode(data: str) -> Optional[str]:
    try:
        # Normalize padding
        padding = 4 - (len(data) % 4)
        if padding and padding < 4:
            data += "=" * padding
        decoded = base64.b64decode(data, validate=False)
        return decoded.decode("utf-8", errors="ignore")
    except Exception:
        return None


PROTOCOL_PREFIXES = [
    "vmess://",
    "vless://",
    "trojan://",
    "ss://",
    "ssr://",
    "hysteria2://",
]

RATE_LIMIT_STATUS = {403, 429, 503, 509}
RATE_LIMIT_BODY_HINTS = [
    "rate limit",
    "too many requests",
    "quota exceeded",
    "exceeded",
    "bandwidth exceeded",
    "流量已用尽",
    "超出配额",
    "请求过多",
]


def _convert_to_gb(value: float, unit: str) -> float:
    unit_low = (unit or "").lower()
    if unit_low.startswith("tb"):
        return value * 1024.0
    if unit_low.startswith("mb"):
        return value / 1024.0
    return value


def extract_traffic_info_from_text(text: str) -> Dict[str, object]:
    """Best-effort extraction of traffic info from subscription response text."""
    info: Dict[str, object] = {}
    try:
        # Common patterns: 总流量/总量/Total, 剩余/Remaining, 已用/Used, 单位 GB/TB/MB
        patterns = [
            (r"总(?:流量|量)[:：]\s*([0-9.]+)\s*(TB|GB|MB)?", "total"),
            (r"剩余(?:流量)?[:：]\s*([0-9.]+)\s*(TB|GB|MB)?", "remaining"),
            (r"已用[:：]\s*([0-9.]+)\s*(TB|GB|MB)?", "used"),
            (r"Total\s*:?\s*([0-9.]+)\s*(TB|GB|MB)?", "total"),
            (r"Remaining\s*:?\s*([0-9.]+)\s*(TB|GB|MB)?", "remaining"),
            (r"Used\s*:?\s*([0-9.]+)\s*(TB|GB|MB)?", "used"),
        ]
        for pat, key in patterns:
            m = re.search(pat, text, flags=re.IGNORECASE)
            if m:
                val = float(m.group(1))
                unit = m.group(2) or "GB"
                gb = round(_convert_to_gb(val, unit), 2)
                if key == "total":
                    info["total_traffic"] = gb
                elif key == "remaining":
                    info["remaining_traffic"] = gb
                elif key == "used":
                    info["used_traffic"] = gb
                info["traffic_unit"] = "GB"
        # Derive missing
        total = info.get("total_traffic")
        remaining = info.get("remaining_traffic")
        used = info.get("used_traffic")
        if total is not None and remaining is not None and used is None:
            info["used_traffic"] = round(total - remaining, 2)
        if total is not None and used is not None and remaining is None:
            info["remaining_traffic"] = round(total - used, 2)
    except Exception:
        pass
    return info


def split_subscription_content_to_lines(raw_bytes: bytes) -> List[str]:
    """Attempt to parse a subscription response body into node lines."""
    text = raw_bytes.decode("utf-8", errors="ignore")
    # Fast path: already contains protocol lines
    if any(p in text for p in PROTOCOL_PREFIXES):
        lines = [ln.strip() for ln in text.replace("\r", "\n").split("\n")]
        return [ln for ln in lines if ln]
    # Try base64 decode
    decoded = safe_b64_decode(text.strip())
    if decoded and any(p in decoded for p in PROTOCOL_PREFIXES):
        lines = [ln.strip() for ln in decoded.replace("\r", "\n").split("\n")]
        return [ln for ln in lines if ln]
    return []


def normalize_node_line(line: str) -> Optional[str]:
    """Basic normalization for dedup: trim and unify some encodings."""
    line = line.strip()
    if not line:
        return None
    # Drop obvious invalids
    if not any(line.startswith(p) for p in PROTOCOL_PREFIXES):
        return None
    return line


def normalize_subscribe_url(raw_url: str) -> Optional[str]:
    """Normalize subscribe URL and drop placeholders.
    - HTML unescape (&amp; -> &)
    - Keep scheme/netloc/path and allowed query keys (token, optional flag)
    - Trim trailing non-URL garbage (stats appended)
    - Filter placeholders like 'xxxx' host or token
    """
    if not raw_url:
        return None
    candidate = html_lib.unescape(raw_url.strip())
    safe_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~:/?#[]@!$&'()*+,;=%")
    trimmed = []
    for ch in candidate:
        if ch in safe_chars:
            trimmed.append(ch)
        else:
            break
    candidate = "".join(trimmed)
    try:
        pu = urlparse(candidate)
        if not pu.scheme or not pu.netloc:
            return None
        if "api/v1/client/subscribe" not in pu.path:
            return None
        host_low = pu.netloc.lower()
        if "xxxx" in host_low or "your-provider.com" in host_low:
            return None
        qs = parse_qs(pu.query or "", keep_blank_values=False)
        token_list = qs.get("token", [])
        if not token_list:
            return None
        token = token_list[0]
        if not re.fullmatch(r"[A-Za-z0-9]+", token):
            return None
        if token.lower() == "xxxx":
            return None
        out_qs = {"token": token}
        if "flag" in qs and re.fullmatch(r"[A-Za-z0-9]+", qs["flag"][0]):
            out_qs["flag"] = qs["flag"][0]
        new_query = urlencode(out_qs)
        normalized = urlunparse((pu.scheme, pu.netloc, pu.path, "", new_query, ""))
        return normalized
    except Exception:
        return None


REGION_KEYWORDS = {
    "hk": ["hk", "hongkong", "hong kong", "🇭🇰", "香港"],
    "sg": ["sg", "singapore", "🇸🇬", "新加坡"],
    "jp": ["jp", "japan", "🇯🇵", "日本"],
    "tw": ["tw", "taiwan", "🇹🇼", "台湾", "臺灣"],
    "us": ["us", "united states", "usa", "🇺🇸", "美国", "美國"],
    "eu": ["eu", "europe", "🇪🇺", "欧", "歐"],
}


def classify_protocol(line: str) -> Optional[str]:
    for p in ["ss", "vmess", "vless", "trojan", "hysteria2", "ssr"]:
        if line.startswith(f"{p}://"):
            return p
    return None


def classify_region_heuristic(line: str) -> Optional[str]:
    # Try to use suffix name after '#'
    display = None
    if "#" in line:
        display = line.split("#", 1)[1]
    else:
        display = line
    low = display.lower()
    for region, keys in REGION_KEYWORDS.items():
        for k in keys:
            if k in low:
                return region
    return None


def fetch_subscription(url: str, timeout_sec: int = 12) -> Tuple[Optional[bytes], Optional[int], Optional[str], Optional[float]]:
    start = time.perf_counter()
    try:
        resp = requests.get(url, timeout=timeout_sec, verify=False)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        body = resp.content or b""
        if resp.status_code == 200 and body:
            return body, resp.status_code, None, elapsed_ms
        sample = ""
        if body and len(body) < 4096:
            try:
                sample = body.decode("utf-8", errors="ignore").lower()
            except Exception:
                sample = ""
        return None, resp.status_code, sample, elapsed_ms
    except Exception as e:
        return None, None, str(e), None


def validate_subscription_url(url: str, timeout_sec: int = 8) -> Tuple[bool, Optional[int], Optional[str], Optional[float]]:
    start = time.perf_counter()
    try:
        resp = requests.get(url, timeout=timeout_sec, stream=True, verify=False)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        code = resp.status_code
        if code != 200:
            return False, code, None, elapsed_ms
        cl = resp.headers.get("Content-Length")
        if cl is not None:
            try:
                if int(cl) < 64:
                    return False, code, None, elapsed_ms
            except Exception:
                pass
        return True, code, None, elapsed_ms
    except Exception as e:
        return False, None, str(e), None


def load_rate_limit_state(path: str) -> Dict[str, dict]:
    data = read_json(path, {})
    if isinstance(data, dict):
        return data
    return {}


def should_skip_due_to_backoff(rate_state: Dict[str, dict], url: str, now_ts: float) -> bool:
    info = rate_state.get(url)
    if not info:
        return False
    next_ok = info.get("next_allowed_at", 0)
    try:
        return now_ts < float(next_ok)
    except Exception:
        return False


def mark_rate_limited(rate_state: Dict[str, dict], url: str, now_ts: float, reason: str) -> None:
    info = rate_state.get(url, {})
    hits = int(info.get("hits", 0)) + 1
    base_minutes = 15 * (2 ** (hits - 1))
    wait_minutes = min(base_minutes, 24 * 60)
    next_allowed_at = now_ts + wait_minutes * 60
    rate_state[url] = {
        "hits": hits,
        "last_reason": reason,
        "last_at": now_ts,
        "next_allowed_at": next_allowed_at,
    }


def merge_urls(*url_lists: Iterable[str]) -> List[str]:
    dedup: Set[str] = set()
    for lst in url_lists:
        for u in lst:
            if not u:
                continue
            dedup.add(u.strip())
    return list(dedup)


def load_candidate_urls(base_dir: str, data_dir: str) -> List[str]:
    # from static seeds
    seeds = read_text_file_lines(os.path.join(base_dir, "api_urls.txt"))
    # from discovered results
    discovered = []
    discovered_path = os.path.join(base_dir, "discovered_urls.json")
    djson = read_json(discovered_path, [])
    if isinstance(djson, list):
        discovered = [str(x) for x in djson]
    # from scraper results
    results = []
    results_path = os.path.join(base_dir, "api_urls_results.json")
    rjson = read_json(results_path, [])
    if isinstance(rjson, list):
        # rjson might be list of url strings or objects
        for item in rjson:
            if isinstance(item, str):
                results.append(item)
            elif isinstance(item, dict):
                url = item.get("url") or item.get("api_url")
                if url:
                    results.append(str(url))
    # from history
    history = []
    history_json = read_json(os.path.join(data_dir, "history_urls.json"), [])
    if isinstance(history_json, list):
        history = [str(x) for x in history_json]
    return merge_urls(seeds, discovered, results, history)


def ensure_dirs(output_dir: str) -> Dict[str, str]:
    paths = {
        "root": output_dir,
        "sub": os.path.join(output_dir, "sub"),
        "regions": os.path.join(output_dir, "sub", "regions"),
        "proto": os.path.join(output_dir, "sub", "proto"),
        "providers": os.path.join(output_dir, "sub", "providers"),
    }
    for p in paths.values():
        os.makedirs(p, exist_ok=True)
    return paths


def write_text(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def generate_index_html(base_url_paths: Dict[str, str], health: Dict[str, object]) -> str:
    # Enhanced static HTML with richer health/status info
    ts = health.get("build_time_utc", "")
    ts_cn = health.get("build_time_cn", "")
    next_ts = health.get("next_run_utc", "")
    next_ts_cn = health.get("next_run_cn", "")
    total_sources = health.get("source_total", 0)
    alive_sources = health.get("source_alive", 0)
    nodes_total = health.get("nodes_total", 0)
    sources_new = health.get("sources_new", 0)
    sources_removed = health.get("sources_removed", 0)
    quota_left = health.get("quota_total_left", 0)
    quota_cap = health.get("quota_total_capacity", 0)
    keys_total = health.get("keys_total", 0)
    keys_ok = health.get("keys_ok", 0)
    github_urls_count = health.get("github_urls_count", 0)
    google_urls_count = health.get("google_urls_count", 0)
    protocol_counts = health.get("protocol_counts", {}) or {}
    ss_n = protocol_counts.get("ss", 0)
    vmess_n = protocol_counts.get("vmess", 0)
    vless_n = protocol_counts.get("vless", 0)
    trojan_n = protocol_counts.get("trojan", 0)
    hy2_n = protocol_counts.get("hysteria2", 0)
    auth_hash = health.get("auth_sha256", "")
    template = """
<!doctype html>
<html lang=\"zh-CN\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>Google SSR Actions - 订阅聚合</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 0; background: #f7fafc; }}
.wrap {{ max-width: 1080px; margin: 0 auto; padding: 28px; }}
.header {{ display:flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px; }}
.subtitle {{ color:#6b7280; margin-top: 4px; }}
.stats {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(140px,1fr)); gap: 12px; margin: 16px 0 24px; }}
.stat {{ background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:14px; text-align:center; }}
.stat .num {{ font-size: 20px; font-weight: 700; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }}
.card {{ background:#fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 16px; }}
.card h3 {{ margin: 0 0 10px; font-size: 16px; }}
code {{ background:#f3f4f6; padding: 2px 6px; border-radius: 4px; }}
small {{ color: #6b7280; }}
</style>
<script>
const AUTH_HASH = "{auth_hash}";
async function sha256(message) {{
  const msgBuffer = new TextEncoder().encode(message);
  const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}}
async function gate() {{
  if (!AUTH_HASH) {{
    document.documentElement.style.display = '';
    return;
  }}
  let ok = false;
  for (let i = 0; i < 3; i++) {{
    const pwd = window.prompt('请输入访问密码');
    if (pwd === null) break;
    const h = await sha256(pwd);
    if (h.toLowerCase() === AUTH_HASH.toLowerCase()) {{ ok = true; break; }}
    alert('密码错误');
  }}
  if (!ok) {{ document.body.innerHTML = '<p style="margin:24px;color:#ef4444">未授权访问</p>'; return; }}
  document.documentElement.style.display = '';
}}
document.documentElement.style.display = 'none';
document.addEventListener('DOMContentLoaded', gate);
</script>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"header\">
      <h1>Google SSR Actions</h1>
      <small>构建时间(中国时区)：{ts_cn}</small>
    </div>
    <div class=\"subtitle\">源 {alive_sources}/{total_sources} · 节点 {nodes_total} · 新增 {sources_new} · 移除 {sources_removed}</div>

    <div class=\"stats\">
      <div class=\"stat\"><div class=\"num\">{quota_left}</div><div>剩余额度</div></div>
      <div class=\"stat\"><div class=\"num\">{quota_cap}</div><div>总额度</div></div>
      <div class=\"stat\"><div class=\"num\">{keys_ok}/{keys_total}</div><div>可用密钥/总密钥</div></div>
      <div class=\"stat\"><div class=\"num\">{next_ts_cn}</div><div>下次更新时间(中国时区)</div></div>
    </div>

    <div class=\"grid\">
      <div class=\"card\">
        <h3>订阅文件</h3>
        <ul>
          <li><a href=\"sub/all.txt\"><code>sub/all.txt</code></a> 全量订阅</li>
          <li><a href=\"sub/all.yaml\"><code>sub/all.yaml</code></a> Clash配置</li>
        </ul>
      </div>

      <div class=\"card\">
        <h3>URL 源</h3>
        <ul>
          <li><a href=\"sub/urls.txt\"><code>urls.txt</code></a> 当前可用源</li>
          <li><a href=\"sub/all_urls.txt\"><code>all_urls.txt</code></a> 完整源列表</li>
          <li><a href=\"sub/google_urls.txt\"><code>google_urls.txt</code></a> Google发现（{google_urls_count}）</li>
          <li><a href=\"sub/github_urls.txt\"><code>github_urls.txt</code></a> GitHub发现（{github_urls_count}）</li>
        </ul>
      </div>

      <div class=\"card\">
        <h3>协议分布</h3>
        <ul>
          <li>SS：{ss_n}</li>
          <li>VMess：{vmess_n}</li>
          <li>VLESS：{vless_n}</li>
          <li>Trojan：{trojan_n}</li>
          <li>Hysteria2：{hy2_n}</li>
        </ul>
      </div>

      <div class=\"card\">
        <h3>源详细信息</h3>
        <p><small>以下为每个订阅URL的可用性、节点与流量概览（仅显示可用源）。</small></p>
        <div id=\"url-meta\"><small>加载中...</small></div>
        <script>
        async function loadMeta() {{
          try {{
            const res = await fetch('sub/url_meta.json', { cache: 'no-cache' });
            if (!res.ok) throw new Error('fetch failed');
            const data = await res.json();
            const rows = data.map(function(item){{
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
          }} catch(e) {{
            document.getElementById('url-meta').innerHTML = '<small>未获取到源详情</small>';
          }}
        }}
        loadMeta();
        </script>
      </div>

      <div class=\"card\">
        <h3>辅助输出</h3>
        <ul>
          <li><a href=\"sub/github.txt\"><code>github.txt</code></a> GitHub节点</li>
          <li><a href=\"sub/proto/ss-base64.txt\"><code>ss-base64.txt</code></a> SS Base64</li>
          <li><a href=\"health.json\"><code>health.json</code></a> 健康信息</li>
        </ul>
      </div>
    </div>

    <p><small>仅展示可用源（自动过滤失效/超额/限速来源）。</small></p>
  </div>
</body>
</html>
"""
    # Replace tokens to avoid f-string parsing issues
    mapping = {
        "{ts}": str(ts),
        "{ts_cn}": str(ts_cn),
        "{next_ts}": str(next_ts),
        "{next_ts_cn}": str(next_ts_cn),
        "{total_sources}": str(total_sources),
        "{alive_sources}": str(alive_sources),
        "{nodes_total}": str(nodes_total),
        "{sources_new}": str(sources_new),
        "{sources_removed}": str(sources_removed),
        "{quota_left}": str(quota_left),
        "{quota_cap}": str(quota_cap),
        "{keys_total}": str(keys_total),
        "{keys_ok}": str(keys_ok),
        "{github_urls_count}": str(github_urls_count),
        "{google_urls_count}": str(google_urls_count),
        "{ss_n}": str(ss_n),
        "{vmess_n}": str(vmess_n),
        "{vless_n}": str(vless_n),
        "{trojan_n}": str(trojan_n),
        "{hy2_n}": str(hy2_n),
        "{auth_hash}": str(auth_hash),
    }
    for k, v in mapping.items():
        template = template.replace(k, v)
    return template


def main():
    parser = argparse.ArgumentParser(description="Aggregate subscription URLs and generate outputs")
    parser.add_argument("--output-dir", required=True, help="Directory to write outputs, e.g., dist")
    parser.add_argument("--max", type=int, default=1200, help="Max nodes in all.txt")
    parser.add_argument("--dedup", action="store_true", help="Enable deduplication")
    parser.add_argument("--history", default=os.path.join(PROJECT_ROOT, "..", "data", "history_urls.json"))
    parser.add_argument("--live-out", default=os.path.join(PROJECT_ROOT, "..", "data", "live_urls.json"))
    parser.add_argument("--skip-scrape", action="store_true", help="Skip running one-shot scraper")
    parser.add_argument("--public-base", default="", help="Public base URL for Pages, e.g., https://USER.github.io/REPO")
    parser.add_argument("--min-searches-left", type=int, default=5, help="If SerpAPI total remaining below this, skip scrape")
    parser.add_argument("--github-discovery", action="store_true", help="Enable GitHub search discovery channel")
    parser.add_argument("--emit-health", action="store_true", help="Emit health.json")
    parser.add_argument("--emit-index", action="store_true", help="Emit index.html")
    args = parser.parse_args()

    # Normalize paths
    output_dir = os.path.abspath(args.output_dir)
    data_dir = os.path.abspath(os.path.join(PROJECT_ROOT, "..", "data"))
    os.makedirs(data_dir, exist_ok=True)
    live_out_path = os.path.abspath(args.live_out)
    # Load previous live for diff
    prev_live_urls: List[str] = []
    try:
        prev_live_urls = read_json(live_out_path, [])
        if not isinstance(prev_live_urls, list):
            prev_live_urls = []
    except Exception:
        prev_live_urls = []

    # Optional: run one-shot scrape to refresh discovered URLs (respect SerpAPI quota)
    if not args.skip_scrape:
        try:
            from enhanced_key_manager import EnhancedSerpAPIKeyManager  # type: ignore
            mgr = EnhancedSerpAPIKeyManager(keys_file=os.path.join(PROJECT_ROOT, "keys"))
            quotas = mgr.check_all_quotas(force_refresh=True)
            total_left = sum(q.get("total_searches_left", 0) for q in quotas if q.get("success"))
            if total_left < args.min_searches_left:
                print(f"[info] SerpAPI remaining {total_left} < {args.min_searches_left}, skip scrape this round")
            else:
                from google_api_scraper_enhanced import EnhancedGoogleAPIScraper  # type: ignore
                scraper = EnhancedGoogleAPIScraper()
                scraper.run_scraping_task()
        except Exception as e:
            print(f"[warn] scrape step skipped or failed: {e}")

    # Always compute quota summary for health (best-effort)
    quota_total_left = 0
    quota_total_cap = 0
    keys_total = 0
    keys_ok = 0
    try:
        from enhanced_key_manager import EnhancedSerpAPIKeyManager  # type: ignore
        mgr2 = EnhancedSerpAPIKeyManager(keys_file=os.path.join(PROJECT_ROOT, "keys"))
        quotas2 = mgr2.check_all_quotas(force_refresh=True)
        keys_total = len(quotas2)
        for q in quotas2:
            if q.get("success"):
                keys_ok += 1
                quota_total_left += int(q.get("total_searches_left", 0) or 0)
                quota_total_cap += int(q.get("searches_per_month", 0) or 0)
    except Exception:
        pass

    # Load candidate URL set
    raw_candidates = load_candidate_urls(PROJECT_ROOT, data_dir)
    candidates = [u for u in (normalize_subscribe_url(u) for u in raw_candidates) if u]
    gh_urls: List[str] = []
    if args.github_discovery:
        try:
            gh_urls = discover_from_github(defaults=True)
            if gh_urls:
                gh_norm = [u for u in (normalize_subscribe_url(u) for u in gh_urls) if u]
                candidates = merge_urls(candidates, gh_norm)
            else:
                print("[info] github discovery returned 0 urls")
        except Exception as e:
            print(f"[warn] github discovery failed: {e}")
    candidates = sorted(set(candidates))

    # Load/prepare rate limit state
    rate_path = os.path.join(data_dir, "rate_limit.json")
    rate_state = load_rate_limit_state(rate_path)
    now_ts = time.time()

    # Validate URLs quickly (without proxy) with backoff
    alive_urls: List[str] = []
    url_latency_ms: Dict[str, float] = {}
    for u in candidates:
        if should_skip_due_to_backoff(rate_state, u, now_ts):
            continue
        ok, code, err, lat_ms = validate_subscription_url(u)
        if ok:
            alive_urls.append(u)
            if lat_ms is not None:
                url_latency_ms[u] = lat_ms
        else:
            if code in RATE_LIMIT_STATUS:
                mark_rate_limited(rate_state, u, now_ts, f"http {code}")
            elif err:
                low = err.lower()
                if any(h in low for h in RATE_LIMIT_BODY_HINTS):
                    mark_rate_limited(rate_state, u, now_ts, "body-hint")

    # Persist history/live
    merged_history = sorted(set(candidates))
    write_json(os.path.join(data_dir, "history_urls.json"), merged_history)
    write_json(os.path.join(data_dir, "live_urls.json"), alive_urls)
    write_json(rate_path, rate_state)

    # Fetch nodes
    all_nodes: List[str] = []
    per_url_latency_nodes: Dict[str, float] = {}
    for u in alive_urls:
        if should_skip_due_to_backoff(rate_state, u, now_ts):
            continue
        body, code, sample, lat_ms = fetch_subscription(u)
        if not body:
            if code in RATE_LIMIT_STATUS:
                mark_rate_limited(rate_state, u, now_ts, f"http {code}")
            elif sample and any(h in sample for h in RATE_LIMIT_BODY_HINTS):
                mark_rate_limited(rate_state, u, now_ts, "body-hint")
            continue
        lines = split_subscription_content_to_lines(body)
        for ln in lines:
            n = normalize_node_line(ln)
            if n:
                all_nodes.append(n)
        if lat_ms is not None:
            per_url_latency_nodes[u] = lat_ms

    # Deduplicate and cap
    if args.dedup:
        all_nodes = list(dict.fromkeys(all_nodes))
    if args.max and len(all_nodes) > args.max:
        # sort by source latency as a heuristic: prefer faster sources first
        def score(line: str) -> float:
            # tie-breaker by protocol preference can be added here
            return min([per_url_latency_nodes.get(u, 1e9) for u in alive_urls])
        all_nodes = all_nodes[: args.max]

    # Sort preference: stable (alive url order) is roughly preserved by collection order
    # Protocol slices
    proto_to_nodes: Dict[str, List[str]] = defaultdict(list)
    for ln in all_nodes:
        proto = classify_protocol(ln)
        if proto:
            proto_to_nodes[proto].append(ln)

    # Region slices
    region_to_nodes: Dict[str, List[str]] = {k: [] for k in REGION_KEYWORDS.keys()}
    for ln in all_nodes:
        region = classify_region_heuristic(ln)
        if region and region in region_to_nodes:
            region_to_nodes[region].append(ln)

    # Ensure directories
    paths = ensure_dirs(output_dir)

    # Write outputs
    write_text(os.path.join(paths["sub"], "all.txt"), "\n".join(all_nodes) + ("\n" if all_nodes else ""))
    # Clash configuration YAML using proxy-providers pointing to a provider file we also publish
    if args.public_base:
        # publish a provider list (just URIs) so Clash can ingest it predictably
        provider_list = {"proxies": all_nodes}
        write_text(os.path.join(paths["providers"], "all.yaml"), yaml.safe_dump(provider_list, allow_unicode=True, sort_keys=False))
        provider_url = args.public_base.rstrip("/") + "/sub/providers/all.yaml"
        clash_yaml = {
            "mixed-port": 7890,
            "allow-lan": False,
            "mode": "rule",
            "log-level": "info",
            "proxy-providers": {
                "all": {
                    "type": "http",
                    "url": provider_url,
                    "path": "./providers/all.yaml",
                    "interval": 3600,
                    "health-check": {
                        "enable": True,
                        "url": "http://www.gstatic.com/generate_204",
                        "interval": 600,
                    },
                }
            },
            "proxy-groups": [
                {"name": "Node-Select", "type": "select", "use": ["all"], "proxies": ["Auto", "DIRECT"]},
                {"name": "Auto", "type": "url-test", "use": ["all"], "url": "http://www.gstatic.com/generate_204", "interval": 300},
                {"name": "Media", "type": "select", "proxies": ["Node-Select", "Auto", "DIRECT"]},
                {"name": "Telegram", "type": "select", "proxies": ["Node-Select", "DIRECT"]},
                {"name": "Microsoft", "type": "select", "proxies": ["DIRECT", "Node-Select"]},
                {"name": "Apple", "type": "select", "proxies": ["DIRECT", "Node-Select"]},
                {"name": "Final", "type": "select", "proxies": ["Node-Select", "DIRECT", "Auto"]},
            ],
            "rule-providers": {
                "LocalAreaNetwork": {
                    "type": "http", "behavior": "classical",
                    "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/LocalAreaNetwork.list",
                    "path": "./rules/LocalAreaNetwork.list", "interval": 86400
                },
                "UnBan": {
                    "type": "http", "behavior": "classical",
                    "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/UnBan.list",
                    "path": "./rules/UnBan.list", "interval": 86400
                },
                "BanAD": {
                    "type": "http", "behavior": "classical",
                    "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanAD.list",
                    "path": "./rules/BanAD.list", "interval": 86400
                },
                "BanProgramAD": {
                    "type": "http", "behavior": "classical",
                    "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanProgramAD.list",
                    "path": "./rules/BanProgramAD.list", "interval": 86400
                },
                "GoogleFCM": {
                    "type": "http", "behavior": "classical",
                    "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Ruleset/GoogleFCM.list",
                    "path": "./rules/GoogleFCM.list", "interval": 86400
                },
                "Telegram": {
                    "type": "http", "behavior": "classical",
                    "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Telegram.list",
                    "path": "./rules/Telegram.list", "interval": 86400
                },
                "ProxyMedia": {
                    "type": "http", "behavior": "classical",
                    "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ProxyMedia.list",
                    "path": "./rules/ProxyMedia.list", "interval": 86400
                },
                "Microsoft": {
                    "type": "http", "behavior": "classical",
                    "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Microsoft.list",
                    "path": "./rules/Microsoft.list", "interval": 86400
                },
                "Apple": {
                    "type": "http", "behavior": "classical",
                    "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Apple.list",
                    "path": "./rules/Apple.list", "interval": 86400
                },
                "ChinaDomain": {
                    "type": "http", "behavior": "classical",
                    "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ChinaDomain.list",
                    "path": "./rules/ChinaDomain.list", "interval": 86400
                },
                "ChinaCompanyIp": {
                    "type": "http", "behavior": "ipcidr",
                    "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ChinaCompanyIp.list",
                    "path": "./rules/ChinaCompanyIp.list", "interval": 86400
                }
            },
            "rules": [
                "RULE-SET,LocalAreaNetwork,DIRECT",
                "RULE-SET,UnBan,DIRECT",
                "RULE-SET,BanAD,REJECT",
                "RULE-SET,BanProgramAD,REJECT",
                "RULE-SET,GoogleFCM,Node-Select",
                "RULE-SET,Telegram,Node-Select",
                "RULE-SET,ProxyMedia,Media",
                "RULE-SET,Microsoft,Microsoft",
                "RULE-SET,Apple,Apple",
                "RULE-SET,ChinaDomain,DIRECT",
                "RULE-SET,ChinaCompanyIp,DIRECT",
                "GEOIP,CN,DIRECT",
                "MATCH,Final",
            ],
        }
        write_text(os.path.join(paths["sub"], "all.yaml"), yaml.safe_dump(clash_yaml, allow_unicode=True, sort_keys=False))
    # 写入各种URL文件
    write_text(os.path.join(paths["sub"], "urls.txt"), "\n".join(alive_urls) + ("\n" if alive_urls else ""))
    write_text(os.path.join(paths["sub"], "all_urls.txt"), "\n".join(alive_urls) + ("\n" if alive_urls else ""))
    
    # 分离GitHub和Google搜索发现的URL
    github_alive_urls: List[str] = []
    google_alive_urls: List[str] = []
    if gh_urls:
        gh_set_urls = set([u for u in (normalize_subscribe_url(u) for u in gh_urls) if u])
        github_alive_urls = [u for u in alive_urls if u in gh_set_urls]
        write_text(os.path.join(paths["sub"], "github_urls.txt"), "\n".join(github_alive_urls) + ("\n" if github_alive_urls else ""))
        
        # Google搜索发现的URL（非GitHub来源）
        google_alive_urls = [u for u in alive_urls if u not in gh_set_urls]
        write_text(os.path.join(paths["sub"], "google_urls.txt"), "\n".join(google_alive_urls) + ("\n" if google_alive_urls else ""))
    else:
        # 如果没有GitHub发现的URL，所有URL都来自Google搜索
        write_text(os.path.join(paths["sub"], "github_urls.txt"), "")
        write_text(os.path.join(paths["sub"], "google_urls.txt"), "\n".join(alive_urls) + ("\n" if alive_urls else ""))

    for region, nodes in region_to_nodes.items():
        write_text(os.path.join(paths["regions"], f"{region}.txt"), "\n".join(nodes) + ("\n" if nodes else ""))

    for proto in ["ss", "vmess", "vless", "trojan", "hysteria2"]:
        nodes = proto_to_nodes.get(proto, [])
        write_text(os.path.join(paths["proto"], f"{proto}.txt"), "\n".join(nodes) + ("\n" if nodes else ""))

    # Extra: Shadowsocks base64 subscription for legacy SS clients
    ss_nodes = proto_to_nodes.get("ss", [])
    if ss_nodes:
        ss_raw = ("\n".join(ss_nodes) + "\n").encode("utf-8")
        ss_b64 = base64.b64encode(ss_raw).decode("ascii")
        write_text(os.path.join(paths["proto"], "ss-base64.txt"), ss_b64 + "\n")

    # Optional: GitHub-only node output
    if gh_urls:
        gh_set = set(gh_urls)
        gh_alive = [u for u in alive_urls if u in gh_set]
        gh_nodes: List[str] = []
        for u in gh_alive:
            if should_skip_due_to_backoff(rate_state, u, now_ts):
                continue
            body, code, sample, _ = fetch_subscription(u)
            if not body:
                if code in RATE_LIMIT_STATUS:
                    mark_rate_limited(rate_state, u, now_ts, f"http {code}")
                elif sample and any(h in sample for h in RATE_LIMIT_BODY_HINTS):
                    mark_rate_limited(rate_state, u, now_ts, "body-hint")
                continue
            lines = split_subscription_content_to_lines(body)
            for ln in lines:
                n = normalize_node_line(ln)
                if n:
                    gh_nodes.append(n)
        if args.dedup:
            gh_nodes = list(dict.fromkeys(gh_nodes))
        write_text(os.path.join(paths["sub"], "github.txt"), "\n".join(gh_nodes) + ("\n" if gh_nodes else ""))

    # Health info
    # Build per-URL metadata (availability, nodes, traffic) for index table
    url_meta: List[Dict[str, object]] = []
    for u in alive_urls:
        meta = {"url": u, "available": True}
        # Try to fetch a small sample for traffic hints
        body, code, sample, lat_ms = fetch_subscription(u)
        meta["response_ms"] = round(lat_ms or 0.0, 1) if lat_ms is not None else None
        if not body:
            meta["available"] = False
            url_meta.append(meta)
            continue
        text_preview = body.decode('utf-8', errors='ignore')[:4000]
        traffic = extract_traffic_info_from_text(text_preview)
        # Estimate protocols by counting prefixes
        pc = {p: 0 for p in ["ss", "vmess", "vless", "trojan", "hysteria2", "ssr"]}
        lines = split_subscription_content_to_lines(body)
        for ln in lines:
            c = classify_protocol(ln) or ""
            if c in pc:
                pc[c] += 1
        nodes_total = sum(pc.values())
        proto_text = ", ".join([f"{k}:{v}" for k, v in pc.items() if v > 0])
        meta.update({
            "nodes_total": nodes_total,
            "protocols": proto_text,
            "traffic": {
                "total": traffic.get("total_traffic"),
                "remaining": traffic.get("remaining_traffic"),
                "used": traffic.get("used_traffic"),
                "unit": traffic.get("traffic_unit", "GB"),
            }
        })
        url_meta.append(meta)

    # Health info
    build_dt = datetime.now(timezone.utc)
    # Fixed schedule: every 3 hours
    from datetime import timedelta
    next_dt = build_dt + timedelta(hours=3)
    # China timezone strings
    try:
        cn_tz = ZoneInfo("Asia/Shanghai")
        ts_cn = build_dt.astimezone(cn_tz).strftime("%Y-%m-%d %H:%M:%S")
        next_cn = next_dt.astimezone(cn_tz).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        ts_cn = ""
        next_cn = ""
    sources_new = len(set(alive_urls) - set(prev_live_urls))
    sources_removed = len(set(prev_live_urls) - set(alive_urls))
    protocol_counts = {k: len(v) for k, v in proto_to_nodes.items()}
    # Optional auth: set AUTH_SHA256 env to require password gate
    auth_sha256_env = os.getenv("AUTH_SHA256", "")
    # Optional auth: set AUTH_PLAIN to a simple password; we hash it here to avoid embedding plain text
    auth_plain = os.getenv("AUTH_PLAIN", "")
    auth_sha256_env = os.getenv("AUTH_SHA256", "")
    if auth_plain and not auth_sha256_env:
        try:
            auth_sha256_env = hashlib.sha256(auth_plain.encode("utf-8")).hexdigest()
        except Exception:
            auth_sha256_env = ""

    health = {
        "build_time_utc": build_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "build_time_cn": ts_cn,
        "next_run_utc": next_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "next_run_cn": next_cn,
        "source_total": len(candidates),
        "source_alive": len(alive_urls),
        "sources_new": sources_new,
        "sources_removed": sources_removed,
        "nodes_total": len(all_nodes),
        "protocol_counts": protocol_counts,
        "github_urls_count": len(github_alive_urls),
        "google_urls_count": len(google_alive_urls) if google_alive_urls else (len(alive_urls) if not gh_urls else 0),
        "quota_total_left": quota_total_left,
        "quota_total_capacity": quota_total_cap,
        "keys_total": keys_total,
        "keys_ok": keys_ok,
        "auth_sha256": auth_sha256_env,
    }
    if args.emit_health:
        write_json(os.path.join(output_dir, "health.json"), health)
        # also publish url meta for UI table
        write_json(os.path.join(paths["sub"], "url_meta.json"), url_meta)

    # Index page
    if args.emit_index:
        index_html = generate_index_html(paths, health)
        write_text(os.path.join(output_dir, "index.html"), index_html)

    print(f"[ok] sources: {len(candidates)}, alive: {len(alive_urls)}, nodes: {len(all_nodes)}")


if __name__ == "__main__":
    main()


