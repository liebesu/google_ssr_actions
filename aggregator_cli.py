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
    "hk": ["hk", "hongkong", "hong kong", "🇭🇰", "香港", "hkg"],
    "tw": ["tw", "taiwan", "🇹🇼", "台湾", "臺灣", "taipei", "台北"],
    "sg": ["sg", "singapore", "🇸🇬", "新加坡", "sgp"],
    "us": ["us", "united states", "usa", "🇺🇸", "美国", "美國", "america", "american"],
    "kr": ["kr", "korea", "south korea", "🇰🇷", "韩国", "韓國", "seoul", "首尔", "首爾"],
    "jp": ["jp", "japan", "🇯🇵", "日本", "tokyo", "osaka", "东京", "大阪"],
    "eu": ["eu", "europe", "🇪🇺", "欧", "歐", "germany", "france", "uk", "netherlands"],
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
    try:
        template_path = os.path.join(PROJECT_ROOT, "static", "index.html.tpl")
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
    except Exception:
        return "<html><body><p>index template missing</p></body></html>"

    protocol_counts = health.get("protocol_counts", {}) or {}
    mapping = {
        "__AUTH_HASH__": str(health.get("auth_sha256", "")),
        "__AUTH_USER__": str(health.get("auth_user", "")),
        "__TS__": str(health.get("build_time_utc", "")),
        "__TS_CN__": str(health.get("build_time_cn", "")),
        "__NEXT__": str(health.get("next_run_utc", "")),
        "__NEXT_CN__": str(health.get("next_run_cn", "")),
        "__ALIVE__": str(health.get("source_alive", 0)),
        "__TOTAL__": str(health.get("source_total", 0)),
        "__NODES__": str(health.get("nodes_total", 0)),
        "__NEW__": str(health.get("sources_new", 0)),
        "__REMOVED__": str(health.get("sources_removed", 0)),
        "__DAILY_NEW__": str(health.get("daily_new_urls", 0)),  # 新增：每日新增URL
        "__QLEFT__": str(health.get("quota_total_left", 0)),
        "__QCAP__": str(health.get("quota_total_capacity", 0)),
        "__KOK__": str(health.get("keys_ok", 0)),
        "__KTOTAL__": str(health.get("keys_total", 0)),
        "__GCOUNT__": str(health.get("google_urls_count", 0)),
        "__GHCOUNT__": str(health.get("github_urls_count", 0)),
        "__SS__": str(protocol_counts.get("ss", 0)),
        "__VMESS__": str(protocol_counts.get("vmess", 0)),
        "__VLESS__": str(protocol_counts.get("vless", 0)),
        "__TROJAN__": str(protocol_counts.get("trojan", 0)),
        "__HY2__": str(protocol_counts.get("hysteria2", 0)),
    }
    for k, v in mapping.items():
        template = template.replace(k, v)
    return template


def main():
    parser = argparse.ArgumentParser(description="Aggregate subscription URLs and generate outputs")
    parser.add_argument("--output-dir", required=True, help="Directory to write outputs, e.g., dist")
    parser.add_argument("--max", type=int, default=None, help="Max nodes in all.txt (no limit if not specified)")
    parser.add_argument("--dedup", action="store_true", help="Enable deduplication")
    parser.add_argument("--history", default=os.path.join(PROJECT_ROOT, "data", "history_urls.json"))
    parser.add_argument("--live-out", default=os.path.join(PROJECT_ROOT, "data", "live_urls.json"))
    parser.add_argument("--skip-scrape", action="store_true", help="Skip running one-shot scraper")
    parser.add_argument("--public-base", default="", help="Public base URL for Pages, e.g., https://USER.github.io/REPO")
    parser.add_argument("--min-searches-left", type=int, default=5, help="If SerpAPI total remaining below this, skip scrape")
    parser.add_argument("--github-discovery", action="store_true", help="Enable GitHub search discovery channel")
    parser.add_argument("--emit-health", action="store_true", help="Emit health.json")
    parser.add_argument("--emit-index", action="store_true", help="Emit index.html")
    args = parser.parse_args()

    # Normalize paths
    output_dir = os.path.abspath(args.output_dir)
    data_dir = os.path.abspath(os.path.join(PROJECT_ROOT, "data"))
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

    # Track first-seen dates for URLs
    first_seen_path = os.path.join(data_dir, "url_first_seen.json")
    first_seen_map = read_json(first_seen_path, {})
    if not isinstance(first_seen_map, dict):
        first_seen_map = {}
    try:
        cn_tz = ZoneInfo("Asia/Shanghai")
        date_today = datetime.now(cn_tz).strftime("%Y-%m-%d")
    except Exception:
        date_today = datetime.utcnow().strftime("%Y-%m-%d")

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
    serpapi_keys_detail = []
    try:
        print(f"[info] 尝试加载 SerpAPI 密钥管理器...")
        from enhanced_key_manager import EnhancedSerpAPIKeyManager  # type: ignore
        keys_file_path = os.path.join(PROJECT_ROOT, "keys")
        print(f"[info] 密钥文件路径: {keys_file_path}")
        
        # 检查密钥文件是否存在
        if not os.path.exists(keys_file_path):
            print(f"[warn] 密钥文件不存在: {keys_file_path}")
            # 尝试从环境变量获取密钥
            scraper_keys_env = os.getenv("SCRAPER_KEYS")
            if scraper_keys_env:
                print(f"[info] 从环境变量 SCRAPER_KEYS 获取密钥")
                with open(keys_file_path, 'w') as f:
                    f.write(scraper_keys_env)
                print(f"[info] 已创建密钥文件: {keys_file_path}")
            else:
                print(f"[warn] 环境变量 SCRAPER_KEYS 也未设置")
                serpapi_keys_detail = [{"error": f"Keys file not found and SCRAPER_KEYS env not set"}]
                return
        
        # 检查密钥文件是否为空
        if os.path.exists(keys_file_path):
            with open(keys_file_path, 'r') as f:
                keys_content = f.read().strip()
                if not keys_content:
                    print(f"[warn] 密钥文件为空")
                    serpapi_keys_detail = [{"error": "Keys file is empty"}]
                    return
            # 读取密钥文件内容
            with open(keys_file_path, 'r') as f:
                keys_content = f.read().strip()
                print(f"[info] 密钥文件内容长度: {len(keys_content)}")
                print(f"[info] 密钥行数: {len(keys_content.splitlines())}")
            
            mgr2 = EnhancedSerpAPIKeyManager(keys_file=keys_file_path)
            print(f"[info] 密钥管理器初始化完成，密钥数量: {len(mgr2.api_keys)}")
            
            quotas2 = mgr2.check_all_quotas(force_refresh=True)
            print(f"[info] 检查到 {len(quotas2)} 个密钥的额度信息")
            
            keys_total = len(quotas2)
            for i, q in enumerate(quotas2):
                print(f"[info] 密钥 {i+1}: success={q.get('success')}, left={q.get('total_searches_left')}, total={q.get('searches_per_month')}")
                if q.get("success"):
                    keys_ok += 1
                    quota_total_left += int(q.get("total_searches_left", 0) or 0)
                    quota_total_cap += int(q.get("searches_per_month", 0) or 0)
                # 收集每个 key 的详细信息
                key_info = {
                    "index": i + 1,
                    "success": q.get("success", False),
                    "total_searches_left": q.get("total_searches_left", 0),
                    "searches_per_month": q.get("searches_per_month", 0),
                    "used_searches": q.get("searches_per_month", 0) - q.get("total_searches_left", 0),
                    "reset_date": q.get("reset_date", ""),
                    "error": q.get("error", "") if not q.get("success") else ""
                }
                serpapi_keys_detail.append(key_info)
            
            print(f"[info] SerpAPI 汇总: 可用密钥 {keys_ok}/{keys_total}, 总剩余额度 {quota_total_left}/{quota_total_cap}")
    except Exception as e:
        print(f"[error] SerpAPI 密钥检查失败: {str(e)}")
        import traceback
        traceback.print_exc()
        serpapi_keys_detail = [{"error": f"Failed to load keys: {str(e)}"}]
        
        # 备用方案：尝试从环境变量获取真实密钥信息
        scraper_keys_env = os.getenv("SCRAPER_KEYS")
        if scraper_keys_env:
            actual_keys = [k.strip() for k in scraper_keys_env.split('\n') if k.strip()]
            keys_total = len(actual_keys)
            print(f"[info] 备用方案：从环境变量检测到 {keys_total} 个真实密钥")
            
            # 为每个真实密钥创建状态记录
            serpapi_keys_detail = []
            for i, key in enumerate(actual_keys):
                key_detail = {
                    "index": i + 1,
                "success": False,
                "total_searches_left": 0,
                "searches_per_month": 0,
                "used_searches": 0,
                "reset_date": "",
                    "key_masked": key[:8] + "..." if len(key) > 8 else key,
                    "error": f"Unable to check quota: {str(e)}"
                }
                
                # 简单的密钥格式验证
                if len(key) >= 20 and key.replace('_', '').replace('-', '').isalnum():
                    key_detail["status"] = "key_valid_unchecked"
                else:
                    key_detail["status"] = "key_invalid"
                    key_detail["error"] = "Invalid key format"
                
                serpapi_keys_detail.append(key_detail)
                
            keys_ok = len([k for k in serpapi_keys_detail if k.get("status") == "key_valid_unchecked"])
            print(f"[info] 检测到格式有效的密钥: {keys_ok}/{keys_total}")
        else:
            print(f"[warn] 环境变量 SCRAPER_KEYS 未配置")
            serpapi_keys_detail = [{"error": "No SCRAPER_KEYS environment variable found"}]
    
    # 如果无法获取真实数据，显示错误状态而不是假数据
    if quota_total_left == 0 and quota_total_cap == 0:
        print(f"[error] 无法获取真实的SerpAPI数据，请检查密钥配置")
        # 设置为错误状态，让前端显示实际的错误信息
        if not serpapi_keys_detail:
            serpapi_keys_detail = [{"error": "Unable to fetch real SerpAPI data"}]

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

    # Persist history and current rate-limit state (live list will be written after availability refinement)
    merged_history = sorted(set(candidates))
    write_json(os.path.join(data_dir, "history_urls.json"), merged_history)
    write_json(rate_path, rate_state)
    # Update first-seen dates for any new URLs
    changed_first_seen = False
    for u in merged_history:
        if u not in first_seen_map:
            first_seen_map[u] = date_today
            changed_first_seen = True
    if changed_first_seen:
        write_json(first_seen_path, first_seen_map)

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
    nodes_before_dedup = len(all_nodes)
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

    # Write outputs - 临时使用原始的 all_nodes，稍后会被 verified_nodes 替换
    write_text(os.path.join(paths["sub"], "all.txt"), "\n".join(all_nodes) + ("\n" if all_nodes else ""))
    
    # Clash configuration YAML using proxy-providers pointing to a provider file we also publish
    if args.public_base:
        # publish a provider list (just URIs) so Clash can ingest it predictably
        provider_list = {"proxies": all_nodes}
        write_text(os.path.join(paths["providers"], "all.yaml"), yaml.safe_dump(provider_list, allow_unicode=True, sort_keys=False, default_flow_style=False, indent=2, width=float('inf')))
        provider_url = args.public_base.rstrip("/") + "/sub/providers/all.yaml"
        clash_yaml = {
            "mixed-port": 7890,
            "allow-lan": False,
            "mode": "rule",
            "log-level": "info",
            "proxies": all_nodes,  # 直接包含所有节点
            "proxy-groups": [
                {"name": "Node-Select", "type": "select", "proxies": ["Auto", "DIRECT"] + all_nodes[:50] if len(all_nodes) > 0 else ["Auto", "DIRECT"]},  # 限制前50个节点避免配置过大
                {"name": "Auto", "type": "url-test", "proxies": all_nodes[:30] if len(all_nodes) > 0 else ["DIRECT"], "url": "http://www.gstatic.com/generate_204", "interval": 300},
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
        write_text(os.path.join(paths["sub"], "all.yaml"), yaml.safe_dump(clash_yaml, allow_unicode=True, sort_keys=False, default_flow_style=False, indent=2, width=float('inf')))
        
        # 保持原有的 proxy-providers 版本作为备选 (all_providers.yaml)
        clash_yaml_providers = {
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
            "rule-providers": clash_yaml["rule-providers"],
            "rules": clash_yaml["rules"],
        }
        write_text(os.path.join(paths["sub"], "all_providers.yaml"), yaml.safe_dump(clash_yaml_providers, allow_unicode=True, sort_keys=False, default_flow_style=False, indent=2, width=float('inf')))
    # URL文件的写入改在可用性细化（含流量/配额判定）后执行

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
    parse_ok_count = 0
    # Build a set of GitHub-discovered URLs for source tagging
    gh_norm_set: Set[str] = set()
    try:
        gh_norm_set = set([uu for uu in (normalize_subscribe_url(uu) for uu in gh_urls) if uu]) if gh_urls else set()
    except Exception:
        gh_norm_set = set()

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
        low_preview = text_preview.lower()
        over_quota_hint = any(h in low_preview for h in RATE_LIMIT_BODY_HINTS)
        # Estimate protocols by counting prefixes
        pc = {p: 0 for p in ["ss", "vmess", "vless", "trojan", "hysteria2", "ssr"]}
        lines = split_subscription_content_to_lines(body)
        for ln in lines:
            c = classify_protocol(ln) or ""
            if c in pc:
                pc[c] += 1
        nodes_total = sum(pc.values())
        proto_text = ", ".join([f"{k}:{v}" for k, v in pc.items() if v > 0])
        # per-source provider assets
        sid = hashlib.sha1(u.encode("utf-8")).hexdigest()[:12]
        try:
            host = urlparse(u).netloc
        except Exception:
            host = ""
        provider = host or "unknown"
        # write provider nodes and meta for drill-down page
        try:
            prov_txt_path = os.path.join(paths["providers"], f"{sid}.txt")
            write_text(prov_txt_path, "\n".join(lines) + ("\n" if lines else ""))
            prov_meta = {
                "id": sid,
                "url": u,
                "host": host,
                "provider": provider,
                "nodes_total": nodes_total,
                "protocol_counts": {k: v for k, v in pc.items() if v > 0},
                "traffic": {
                    "total": traffic.get("total_traffic"),
                    "remaining": traffic.get("remaining_traffic"),
                    "used": traffic.get("used_traffic"),
                    "unit": traffic.get("traffic_unit", "GB"),
                },
                "response_ms": meta["response_ms"],
                "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
            write_json(os.path.join(paths["providers"], f"{sid}.json"), prov_meta)
        except Exception:
            pass
        # 结合节点数/配额提示/剩余流量，修正可用性
        remaining_gb = traffic.get("remaining_traffic")
        is_depleted = False
        try:
            if remaining_gb is not None:
                is_depleted = float(remaining_gb) <= 0.0
        except Exception:
            is_depleted = False
        if nodes_total == 0 or over_quota_hint or is_depleted:
            meta["available"] = False
        meta["over_quota"] = bool(over_quota_hint or is_depleted)

        # Quality score estimation: blend latency and parse success
        lat_component = 100.0 - min(100.0, (meta["response_ms"] or 2000.0) / 20.0)
        parse_component = 100.0 if nodes_total > 0 else 0.0
        quality_score = int(round(0.6 * lat_component + 0.4 * parse_component))
        if nodes_total > 0:
            parse_ok_count += 1
        meta.update({
            "nodes_total": nodes_total,
            "protocols": proto_text,
            "id": sid,
            "host": host,
            "provider": provider,
            "source": ("github" if u in gh_norm_set else "google"),
            "first_seen": first_seen_map.get(u, date_today),
            "first_seen_time": datetime.now(cn_tz).strftime("%H:%M:%S"),
            "detail_page": f"source.html?id={sid}",
            "quality_score": quality_score,
            "traffic": {
                "total": traffic.get("total_traffic"),
                "remaining": traffic.get("remaining_traffic"),
                "used": traffic.get("used_traffic"),
                "unit": traffic.get("traffic_unit", "GB"),
            }
        })
        url_meta.append(meta)

    # 二次可用性筛选：仅保留有效且未满额/未用尽且有节点的源
    refined_alive_urls = [m["url"] for m in url_meta if m.get("available")]

    # 只有经过验证的可用源的节点才会被包含在对外提供的订阅文件中
    # 重新获取节点，只从 refined_alive_urls 中获取
    verified_nodes: List[str] = []
    print(f"[info] 从 {len(refined_alive_urls)} 个验证可用源重新获取节点...")
    
    for u in refined_alive_urls:
        if should_skip_due_to_backoff(rate_state, u, now_ts):
            continue
        body, code, sample, lat_ms = fetch_subscription(u)
        if not body:
            continue
        lines = split_subscription_content_to_lines(body)
        for ln in lines:
            n = normalize_node_line(ln)
            if n:
                verified_nodes.append(n)
    
    # 去重和限制数量
    nodes_before_dedup = len(verified_nodes)  # 记录去重前的数量
    if args.dedup:
        verified_nodes = list(dict.fromkeys(verified_nodes))
    if args.max and len(verified_nodes) > args.max:
        verified_nodes = verified_nodes[:args.max]
    
    print(f"[info] 从验证源获取到 {len(verified_nodes)} 个节点用于对外订阅文件")
    
    # 基于验证节点重新进行地区和协议分类
    verified_region_to_nodes: Dict[str, List[str]] = {k: [] for k in REGION_KEYWORDS.keys()}
    verified_region_to_nodes["others"] = []  # 添加"其他地区"分类
    verified_proto_to_nodes: Dict[str, List[str]] = defaultdict(list)
    
    # 主要地区列表（用于判断是否为"其他地区"）
    main_regions = {"hk", "tw", "sg", "us", "kr", "jp"}
    
    for ln in verified_nodes:
        # 地区分类
        region = classify_region_heuristic(ln)
        if region and region in verified_region_to_nodes:
            verified_region_to_nodes[region].append(ln)
        elif not region or region not in main_regions:
            # 未识别的地区或非主要地区，归入"其他地区"
            verified_region_to_nodes["others"].append(ln)
        
        # 协议分类  
        proto = classify_protocol(ln)
        if proto:
            verified_proto_to_nodes[proto].append(ln)
    
    # 更新订阅文件 - 只包含验证可用源的节点
    write_text(os.path.join(paths["sub"], "all.txt"), "\n".join(verified_nodes) + ("\n" if verified_nodes else ""))

    # Clash configuration YAML using proxy-providers pointing to a provider file we also publish
    if args.public_base:
        # publish a provider list (just URIs) so Clash can ingest it predictably
        provider_list = {"proxies": verified_nodes}
        write_text(os.path.join(paths["providers"], "all.yaml"), yaml.safe_dump(provider_list, allow_unicode=True, sort_keys=False, default_flow_style=False, indent=2, width=float('inf')))
        provider_url = args.public_base.rstrip("/") + "/sub/providers/all.yaml"
        clash_yaml = {
            "mixed-port": 7890,
            "allow-lan": False,
            "mode": "rule",
            "log-level": "info",
            "proxies": verified_nodes,  # 直接包含所有节点
            "proxy-groups": [
                {"name": "Node-Select", "type": "select", "proxies": ["Auto", "DIRECT"] + verified_nodes[:50] if len(verified_nodes) > 0 else ["Auto", "DIRECT"]},  # 限制前50个节点避免配置过大
                {"name": "Auto", "type": "url-test", "proxies": verified_nodes[:30] if len(verified_nodes) > 0 else ["DIRECT"], "url": "http://www.gstatic.com/generate_204", "interval": 300},
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
                "GoogleCN": {
                    "type": "http", "behavior": "classical",
                    "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/GoogleCN.list",
                    "path": "./rules/GoogleCN.list", "interval": 86400
                },
                "SteamCN": {
                    "type": "http", "behavior": "classical",
                    "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Ruleset/SteamCN.list",
                    "path": "./rules/SteamCN.list", "interval": 86400
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
                "ProxyGFWlist": {
                    "type": "http", "behavior": "classical",
                    "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ProxyGFWlist.list",
                    "path": "./rules/ProxyGFWlist.list", "interval": 86400
                },
                "ChinaDomain": {
                    "type": "http", "behavior": "classical",
                    "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ChinaDomain.list",
                    "path": "./rules/ChinaDomain.list", "interval": 86400
                },
                "ChinaCompanyIp": {
                    "type": "http", "behavior": "classical",
                    "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ChinaCompanyIp.list",
                    "path": "./rules/ChinaCompanyIp.list", "interval": 86400
                },
                "Download": {
                    "type": "http", "behavior": "classical",
                    "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Download.list",
                    "path": "./rules/Download.list", "interval": 86400
                },
                "ChinaIp": {
                    "type": "http", "behavior": "classical",
                    "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ChinaIp.list",
                    "path": "./rules/ChinaIp.list", "interval": 86400
                }
            },
            "rules": [
                "RULE-SET,LocalAreaNetwork,DIRECT",
                "RULE-SET,UnBan,DIRECT",
                "RULE-SET,BanAD,REJECT",
                "RULE-SET,BanProgramAD,REJECT",
                "RULE-SET,GoogleFCM,DIRECT",
                "RULE-SET,GoogleCN,DIRECT",
                "RULE-SET,SteamCN,DIRECT",
                "RULE-SET,Microsoft,Microsoft",
                "RULE-SET,Apple,Apple",
                "RULE-SET,Telegram,Telegram",
                "RULE-SET,ProxyMedia,Media",
                "RULE-SET,ProxyGFWlist,Node-Select",
                "RULE-SET,ChinaDomain,DIRECT",
                "RULE-SET,ChinaCompanyIp,DIRECT",
                "RULE-SET,Download,DIRECT",
                "GEOIP,CN,DIRECT",
                "RULE-SET,ChinaIp,DIRECT",
                "MATCH,Final"
            ]
        }
        write_text(os.path.join(paths["sub"], "all.yaml"), yaml.safe_dump(clash_yaml, allow_unicode=True, sort_keys=False, default_flow_style=False, indent=2, width=float('inf')))

    # 生成基于验证节点的地区和协议分类文件
    print(f"[info] 生成地区分类文件...")
    for region, nodes in verified_region_to_nodes.items():
        if nodes:  # 只有当地区有节点时才生成文件
            print(f"[info] {region}.txt: {len(nodes)} 个节点")
        write_text(os.path.join(paths["regions"], f"{region}.txt"), "\n".join(nodes) + ("\n" if nodes else ""))
    
    print(f"[info] 生成协议分类文件...")
    for proto in ["ss", "vmess", "vless", "trojan", "hysteria2", "ssr"]:
        nodes = verified_proto_to_nodes.get(proto, [])
        if nodes:  # 只有当协议有节点时才输出日志
            print(f"[info] {proto}.txt: {len(nodes)} 个节点")
        write_text(os.path.join(paths["proto"], f"{proto}.txt"), "\n".join(nodes) + ("\n" if nodes else ""))
    
    # Shadowsocks base64 订阅文件（兼容传统SS客户端）
    ss_nodes = verified_proto_to_nodes.get("ss", [])
    if ss_nodes:
        ss_raw = ("\n".join(ss_nodes) + "\n").encode("utf-8")
        ss_b64 = base64.b64encode(ss_raw).decode("ascii")
        write_text(os.path.join(paths["proto"], "ss-base64.txt"), ss_b64 + "\n")
        print(f"[info] ss-base64.txt: {len(ss_nodes)} 个SS节点（Base64编码）")

    # 写入各种URL文件
    write_json(live_out_path, refined_alive_urls)
    
    # 文件分类说明：
    # 1. all_urls.txt: 完整源列表（包含所有发现的源，无任何过滤）
    # 2. 其他文件: 只包含经过以下验证的可用源：
    #    - 可访问性检查：能否正常访问
    #    - 有效性验证：是否失效 
    #    - 余额检查：是否有剩余流量
    #    - 质量评估：综合性能评分
    
    # urls.txt: 只包含经过分析验证的可用源
    write_text(os.path.join(paths["sub"], "urls.txt"), "\n".join(refined_alive_urls) + ("\n" if refined_alive_urls else ""))
    
    # all_urls.txt: 完整源列表（未经过滤的原始发现源）
    all_discovered_urls = list(candidates)
    write_text(os.path.join(paths["sub"], "all_urls.txt"), "\n".join(all_discovered_urls) + ("\n" if all_discovered_urls else ""))

    # 分离GitHub和Google搜索发现的URL（基于 refined 列表）
    github_alive_urls: List[str] = []
    google_alive_urls: List[str] = []
    if gh_urls:
        try:
            gh_set_urls = set([uu for uu in (normalize_subscribe_url(uu) for uu in gh_urls) if uu])
        except Exception:
            gh_set_urls = set()
        github_alive_urls = [u for u in refined_alive_urls if u in gh_set_urls]
        write_text(os.path.join(paths["sub"], "github_urls.txt"), "\n".join(github_alive_urls) + ("\n" if github_alive_urls else ""))
        # Google搜索发现的URL（非GitHub来源，只包含验证可用的）
        google_alive_urls = [u for u in refined_alive_urls if u not in gh_set_urls]
        write_text(os.path.join(paths["sub"], "google_urls.txt"), "\n".join(google_alive_urls) + ("\n" if google_alive_urls else ""))
    else:
        write_text(os.path.join(paths["sub"], "github_urls.txt"), "")
        write_text(os.path.join(paths["sub"], "google_urls.txt"), "\n".join(refined_alive_urls) + ("\n" if refined_alive_urls else ""))

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
    sources_new = len(set(refined_alive_urls) - set(prev_live_urls))
    sources_removed = len(set(prev_live_urls) - set(refined_alive_urls))
    protocol_counts = {k: len(v) for k, v in proto_to_nodes.items()}
    # Optional auth: set AUTH_SHA256 env to require password gate
    auth_sha256_env = os.getenv("AUTH_SHA256", "")
    # Optional auth: set AUTH_PLAIN to a simple password; we hash it here to avoid embedding plain text
    auth_plain = os.getenv("AUTH_PLAIN", "")
    if auth_plain and not auth_sha256_env:
        try:
            auth_sha256_env = hashlib.sha256(auth_plain.encode("utf-8")).hexdigest()
        except Exception:
            auth_sha256_env = ""
    auth_user = os.getenv("AUTH_USER", "")

    health = {
        "build_time_utc": build_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "build_time_cn": ts_cn,
        "next_run_utc": next_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "next_run_cn": next_cn,
        "source_total": len(candidates),
        "source_alive": len(refined_alive_urls),
        "sources_new": sources_new,
        "sources_removed": sources_removed,
        "daily_new_urls": sum(1 for meta in url_meta if meta.get("first_seen") == date_today),
        "nodes_total": len(verified_nodes),
        "nodes_before_dedup": nodes_before_dedup,
        "nodes_after_dedup": len(verified_nodes),
        "dedup_ratio": round(1.0 - (len(verified_nodes) / nodes_before_dedup), 4) if nodes_before_dedup else 0.0,
        "parse_ok_rate": round((parse_ok_count / max(1, len(alive_urls))), 4),
        "protocol_counts": protocol_counts,
        "github_urls_count": len(github_alive_urls),
        "google_urls_count": len(google_alive_urls) if google_alive_urls else (len(refined_alive_urls) if not gh_urls else 0),
        "quota_total_left": quota_total_left,
        "quota_total_capacity": quota_total_cap,
        "keys_total": keys_total,
        "keys_ok": keys_ok,
        "serpapi_keys_detail": serpapi_keys_detail,
        "auth_sha256": auth_sha256_env,
        "auth_user": auth_user,
    }
    if args.emit_health:
        write_json(os.path.join(output_dir, "health.json"), health)
        # also publish url meta for UI table
        write_json(os.path.join(paths["sub"], "url_meta.json"), url_meta)
        # daily stats for chart: append today's added counts
        try:
            # 读取并更新仓库内的长期历史
            history_path = os.path.join(data_dir, "stats_daily_history.json")
            hist = read_json(history_path, [])
            if not isinstance(hist, list):
                hist = []
            today = build_dt.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
            entry = {
                "date": today,
                "google_added": int(health.get("google_urls_count", 0)),
                "github_added": int(health.get("github_urls_count", 0)),
                "new_total": int(health.get("sources_new", 0)),
                "removed_total": int(health.get("sources_removed", 0)),
                "alive_total": int(health.get("source_alive", 0)),
            }
            # 覆盖当天并限制最大长度（例如一年）
            hist = [e for e in hist if e.get("date") != today] + [entry]
            hist = hist[-365:]
            write_json(history_path, hist)
            
            # 生成增强的7天历史数据，包含更详细的统计信息
            last_7_days = hist[-7:] if len(hist) >= 7 else hist
            enhanced_7day_data = []
            
            for i, day_data in enumerate(last_7_days):
                # 计算当天的详细统计
                day_date = day_data.get("date", "")
                google_added = day_data.get("google_added", 0)
                github_added = day_data.get("github_added", 0)
                new_total = day_data.get("new_total", 0)
                removed_total = day_data.get("removed_total", 0)
                alive_total = day_data.get("alive_total", 0)
                
                # 计算新增总数（Google + GitHub）
                total_added = google_added + github_added
                
                # 计算失效数量（新增 - 净增长）
                net_growth = new_total - removed_total
                failed_count = max(0, total_added - net_growth)
                
                enhanced_day = {
                    "date": day_date,
                    "total_count": alive_total,  # 总存活数量
                    "new_added": total_added,    # 新增总数
                    "google_added": google_added,
                    "github_added": github_added,
                    "failed_count": failed_count,  # 失效数量
                    "removed_count": removed_total,  # 移除数量
                    "net_growth": net_growth,  # 净增长
                    "alive_count": alive_total  # 存活数量
                }
                enhanced_7day_data.append(enhanced_day)
            
            # 将最近60天写入发布目录供前端使用
            stats_path = os.path.join(paths["sub"], "stats_daily.json")
            write_json(stats_path, hist[-60:])
            
            # 写入增强的7天数据供前端使用
            enhanced_7day_path = os.path.join(paths["sub"], "stats_7day_enhanced.json")
            write_json(enhanced_7day_path, enhanced_7day_data)
        except Exception:
            pass

    # Index page
    if args.emit_index:
        index_html = generate_index_html(paths, health)
        write_text(os.path.join(output_dir, "index.html"), index_html)
        # emit drill-down page
        try:
            src_tpl = os.path.join(PROJECT_ROOT, "static", "source.html")
            if os.path.exists(src_tpl):
                with open(src_tpl, "r", encoding="utf-8") as f:
                    write_text(os.path.join(output_dir, "source.html"), f.read())
        except Exception:
            pass
        # emit login page
        try:
            login_tpl = os.path.join(PROJECT_ROOT, "static", "login.html")
            if os.path.exists(login_tpl):
                with open(login_tpl, "r", encoding="utf-8") as f:
                    tpl = f.read()
                tpl = tpl.replace("__AUTH_HASH__", str(health.get("auth_sha256", "")))
                tpl = tpl.replace("__AUTH_USER__", str(health.get("auth_user", "")))
                write_text(os.path.join(output_dir, "login.html"), tpl)
        except Exception:
            pass
        # emit stylesheet
        try:
            css_tpl = os.path.join(PROJECT_ROOT, "static", "styles.css")
            if os.path.exists(css_tpl):
                with open(css_tpl, "r", encoding="utf-8") as f:
                    css_text = f.read()
                write_text(os.path.join(output_dir, "styles.css"), css_text)
        except Exception:
            pass

    print(f"[ok] sources: {len(candidates)}, alive: {len(alive_urls)}, verified: {len(refined_alive_urls)}, nodes: {len(verified_nodes)}")


if __name__ == "__main__":
    main()


