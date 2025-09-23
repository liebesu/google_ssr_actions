#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lightweight GitHub search scraper to discover subscription URLs

Searches provided GitHub search result pages (repositories/issues) for links,
visits each result page, and extracts subscription URLs containing
"api/v1/client/subscribe?token=" and other patterns handled by URLExtractor.

Notes:
- Anonymous scraping with conservative rate limiting; keep volumes low
- This is best-effort discovery; results are merged and deduped upstream
"""

import re
import time
import typing as t
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup  # type: ignore

from url_extractor import URLExtractor  # type: ignore


DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class ScrapeConfig:
    search_urls: t.List[str]
    per_search_limit: int = 20
    request_delay_sec: float = 1.2
    timeout_sec: int = 12


class GitHubURLScraper:
    def __init__(self, config: ScrapeConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": DEFAULT_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
            "Connection": "keep-alive",
        })
        self.extractor = URLExtractor()

    def _fetch_text(self, url: str) -> str:
        try:
            resp = self.session.get(url, timeout=self.config.timeout_sec)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 429:
                # GitHub API rate limit
                import time
                time.sleep(2)  # Wait before retry
                return ""
            return ""
        except Exception as e:
            # Log error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Failed to fetch {url}: {e}")
            return ""

    def _is_issues_search(self, url: str) -> bool:
        return "type=issues" in url

    def _is_repos_search(self, url: str) -> bool:
        return "type=repositories" in url

    def _extract_issue_links(self, html: str) -> t.List[str]:
        if not html:
            return []
        soup = BeautifulSoup(html, "lxml")
        links: t.List[str] = []
        # issue links look like /owner/repo/issues/123 or /owner/repo/discussions/123
        for a in soup.find_all("a", href=True):
            href = a.get("href") or ""
            if not href.startswith("/"):
                continue
            if "/issues/" in href and not href.endswith("/issues"):
                links.append("https://github.com" + href)
        # dedup keep order
        seen: t.Set[str] = set()
        out: t.List[str] = []
        for u in links:
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out

    def _extract_subscribe_urls(self, text: str) -> t.List[str]:
        urls = set()
        # Primary pattern
        pattern = r'https?://[^\s"\'<>()]+api/v1/client/subscribe\?token=[A-Za-z0-9]+'
        for m in re.findall(pattern, text):
            urls.add(m)
        # Use general extractor for other formats
        for u in self.extractor.extract_subscription_urls(text):
            urls.add(u)
        return list(urls)

    def run(self) -> t.List[str]:
        discovered: t.List[str] = []
        for su in self.config.search_urls:
            html = self._fetch_text(su)
            time.sleep(self.config.request_delay_sec)
            if self._is_issues_search(su):
                # Only first 2 pages are provided in seeds; visit each issue page
                issue_links = self._extract_issue_links(html)[: self.config.per_search_limit]
                for link in issue_links:
                    text = self._fetch_text(link)
                    if text:
                        found = self._extract_subscribe_urls(text)
                        if found:
                            discovered.extend(found)
                    time.sleep(self.config.request_delay_sec)
            elif self._is_repos_search(su):
                # Extract URLs directly from list page per requirement
                found = self._extract_subscribe_urls(html)
                if found:
                    discovered.extend(found)
            else:
                # Fallback: scan page text
                found = self._extract_subscribe_urls(html)
                if found:
                    discovered.extend(found)
        # Dedup
        return list(dict.fromkeys(discovered))


def discover_from_github(defaults: bool = True, extra_urls: t.Optional[t.List[str]] = None) -> t.List[str]:
    seeds: t.List[str] = []
    if defaults:
        seeds.extend([
            # Issues: updated desc, first 3 pages for better coverage
            "https://github.com/search?q=%22api%2Fv1%2Fclient%2Fsubscribe%3Ftoken%3D%22&type=issues&s=updated&o=desc&p=1",
            "https://github.com/search?q=%22api%2Fv1%2Fclient%2Fsubscribe%3Ftoken%3D%22&type=issues&s=updated&o=desc&p=2",
            "https://github.com/search?q=%22api%2Fv1%2Fclient%2Fsubscribe%3Ftoken%3D%22&type=issues&s=updated&o=desc&p=3",
            # Repositories: updated desc, first 2 pages
            "https://github.com/search?q=%22api%2Fv1%2Fclient%2Fsubscribe%3Ftoken%3D%22&type=repositories&s=updated&o=desc&p=1",
            "https://github.com/search?q=%22api%2Fv1%2Fclient%2Fsubscribe%3Ftoken%3D%22&type=repositories&s=updated&o=desc&p=2",
            # Additional search patterns
            "https://github.com/search?q=subscribe+token+api&type=issues&s=updated&o=desc&p=1",
            "https://github.com/search?q=clash+subscription&type=issues&s=updated&o=desc&p=1",
        ])
    if extra_urls:
        seeds.extend(extra_urls)

    # Use more conservative rate limiting for GitHub
    config = ScrapeConfig(search_urls=seeds, per_search_limit=15, request_delay_sec=1.5)
    scraper = GitHubURLScraper(config)
    return scraper.run()


