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
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Set, Tuple

import requests

# Ensure local imports resolve relative to this file
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = CURRENT_DIR
sys.path.append(PROJECT_ROOT)

from url_extractor import URLExtractor  # type: ignore


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


def fetch_subscription(url: str, timeout_sec: int = 12) -> Optional[bytes]:
    try:
        resp = requests.get(url, timeout=timeout_sec, verify=False)
        if resp.status_code == 200 and resp.content:
            return resp.content
        return None
    except Exception:
        return None


def validate_subscription_url(url: str, timeout_sec: int = 8) -> bool:
    try:
        resp = requests.get(url, timeout=timeout_sec, stream=True, verify=False)
        if resp.status_code != 200:
            return False
        # Require minimal body size to avoid empty/banned endpoints
        cl = resp.headers.get("Content-Length")
        if cl is not None:
            try:
                if int(cl) < 64:
                    return False
            except Exception:
                pass
        return True
    except Exception:
        return False


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
    }
    for p in paths.values():
        os.makedirs(p, exist_ok=True)
    return paths


def write_text(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def generate_index_html(base_url_paths: Dict[str, str], health: Dict[str, object]) -> str:
    # Minimal static HTML
    ts = health.get("build_time_utc", "")
    total_sources = health.get("source_total", 0)
    alive_sources = health.get("source_alive", 0)
    nodes_total = health.get("nodes_total", 0)
    return f"""
<!doctype html>
<html lang=\"zh-CN\">
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>Subscriptions</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 24px; }}
code, pre {{ background: #f6f8fa; padding: 2px 6px; border-radius: 4px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }}
.card {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; }}
small {{ color: #6b7280; }}
</style>
<h1>订阅聚合</h1>
<p><small>构建时间(UTC)：{ts} · 源 {alive_sources}/{total_sources} · 节点 {nodes_total}</small></p>
<div class=\"grid\">
  <div class=\"card\"><h3>全量 TXT</h3><a href=\"sub/all.txt\"><code>sub/all.txt</code></a></div>
  <div class=\"card\"><h3>源列表</h3><a href=\"sub/urls.txt\"><code>sub/urls.txt</code></a></div>
  <div class=\"card\"><h3>健康信息</h3><a href=\"health.json\"><code>health.json</code></a></div>
  <div class=\"card\"><h3>地区切片</h3>
    <ul>
      <li><a href=\"sub/regions/hk.txt\">hk.txt</a></li>
      <li><a href=\"sub/regions/sg.txt\">sg.txt</a></li>
      <li><a href=\"sub/regions/jp.txt\">jp.txt</a></li>
      <li><a href=\"sub/regions/tw.txt\">tw.txt</a></li>
      <li><a href=\"sub/regions/us.txt\">us.txt</a></li>
      <li><a href=\"sub/regions/eu.txt\">eu.txt</a></li>
    </ul>
  </div>
  <div class=\"card\"><h3>协议切片</h3>
    <ul>
      <li><a href=\"sub/proto/ss.txt\">ss.txt</a></li>
      <li><a href=\"sub/proto/vmess.txt\">vmess.txt</a></li>
      <li><a href=\"sub/proto/vless.txt\">vless.txt</a></li>
      <li><a href=\"sub/proto/trojan.txt\">trojan.txt</a></li>
      <li><a href=\"sub/proto/hysteria2.txt\">hysteria2.txt</a></li>
    </ul>
  </div>
</div>
<p><small>YAML 导出将在下一版本加入。</small></p>
"""


def main():
    parser = argparse.ArgumentParser(description="Aggregate subscription URLs and generate outputs")
    parser.add_argument("--output-dir", required=True, help="Directory to write outputs, e.g., dist")
    parser.add_argument("--max", type=int, default=1200, help="Max nodes in all.txt")
    parser.add_argument("--dedup", action="store_true", help="Enable deduplication")
    parser.add_argument("--history", default=os.path.join(PROJECT_ROOT, "data", "history_urls.json"))
    parser.add_argument("--live-out", default=os.path.join(PROJECT_ROOT, "data", "live_urls.json"))
    parser.add_argument("--skip-scrape", action="store_true", help="Skip running one-shot scraper")
    parser.add_argument("--emit-health", action="store_true", help="Emit health.json")
    parser.add_argument("--emit-index", action="store_true", help="Emit index.html")
    args = parser.parse_args()

    # Normalize paths
    output_dir = os.path.abspath(args.output_dir)
    data_dir = os.path.abspath(os.path.join(PROJECT_ROOT, "data"))
    os.makedirs(data_dir, exist_ok=True)

    # Optional: run one-shot scrape to refresh discovered URLs
    if not args.skip_scrape:
        try:
            from google_api_scraper_enhanced import EnhancedGoogleAPIScraper  # type: ignore

            scraper = EnhancedGoogleAPIScraper()
            # Run a single scraping round synchronously
            scraper.run_scraping_task()
        except Exception as e:
            # Non-fatal in CI
            print(f"[warn] scrape step failed: {e}")

    # Load candidate URL set
    candidates = load_candidate_urls(PROJECT_ROOT, data_dir)
    candidates = sorted(set(candidates))

    # Validate URLs quickly (without proxy)
    alive_urls: List[str] = []
    for u in candidates:
        if validate_subscription_url(u):
            alive_urls.append(u)

    # Persist history/live
    merged_history = sorted(set(candidates))
    write_json(os.path.join(data_dir, "history_urls.json"), merged_history)
    write_json(os.path.join(data_dir, "live_urls.json"), alive_urls)

    # Fetch nodes
    all_nodes: List[str] = []
    for u in alive_urls:
        body = fetch_subscription(u)
        if not body:
            continue
        lines = split_subscription_content_to_lines(body)
        for ln in lines:
            n = normalize_node_line(ln)
            if n:
                all_nodes.append(n)

    # Deduplicate and cap
    if args.dedup:
        all_nodes = list(dict.fromkeys(all_nodes))
    if args.max and len(all_nodes) > args.max:
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
    write_text(os.path.join(paths["sub"], "urls.txt"), "\n".join(alive_urls) + ("\n" if alive_urls else ""))

    for region, nodes in region_to_nodes.items():
        write_text(os.path.join(paths["regions"], f"{region}.txt"), "\n".join(nodes) + ("\n" if nodes else ""))

    for proto in ["ss", "vmess", "vless", "trojan", "hysteria2"]:
        nodes = proto_to_nodes.get(proto, [])
        write_text(os.path.join(paths["proto"], f"{proto}.txt"), "\n".join(nodes) + ("\n" if nodes else ""))

    # Health info
    health = {
        "build_time_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "source_total": len(candidates),
        "source_alive": len(alive_urls),
        "nodes_total": len(all_nodes),
    }
    if args.emit_health:
        write_json(os.path.join(output_dir, "health.json"), health)

    # Index page
    if args.emit_index:
        index_html = generate_index_html(paths, health)
        write_text(os.path.join(output_dir, "index.html"), index_html)

    print(f"[ok] sources: {len(candidates)}, alive: {len(alive_urls)}, nodes: {len(all_nodes)}")


if __name__ == "__main__":
    main()


