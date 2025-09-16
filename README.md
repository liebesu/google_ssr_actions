# google_ssr_actions

自动抓取/合并/去重可用订阅 URL，并每 30 分钟通过 GitHub Actions 生成订阅文件并发布到 GitHub Pages。

## 输出
- 全量 TXT: `https://liebesu.github.io/google_ssr_actions/sub/all.txt`
- 地区切片: `sub/regions/{hk|sg|jp|tw|us|eu}.txt`
- 协议切片: `sub/proto/{ss|vmess|vless|trojan|hysteria2}.txt`
- 源订阅 URL 列表: `sub/urls.txt`

> 订阅可被 Clash Verge Rev 远程 Profile 使用。建议开启“启动时更新”“定时更新”。

## 仓库结构
- `aggregator_cli.py`: 聚合与输出入口（Actions 调用）
- `requirements_scraper.txt`: 运行依赖
- `github_search_scraper.py`: 通过 GitHub 搜索页发现含 `api/v1/client/subscribe?token=` 的订阅 URL
- `data/`: 历史与可用 URL 状态（Actions 自动更新）
  - `history_urls.json`, `live_urls.json`
- `.github/workflows/build-and-publish-subscriptions.yml`: 定时构建与 Pages 发布

## GitHub Secrets（仓库 Settings → Secrets and variables → Actions）
- `SCRAPER_KEYS`（必填）：把本地 `keys` 文件内容原样粘贴（多钥一行）
- `SCRAPER_CONFIG_JSON`（可选）：如需覆盖默认 `scraper_config.json`，粘贴完整 JSON

## 本地测试（可选）
```bash
python aggregator_cli.py --output-dir dist --max 1200 --dedup --skip-scrape --github-discovery --public-base https://liebesu.github.io/google_ssr_actions
```

## 注意
- YAML 导出暂未启用，后续视需要添加。
- 聚合优先：历史稳定来源 > 较低延迟 > 新发现来源。
