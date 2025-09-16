#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
URL提取和清理工具
专门处理包含HTML标签的伪URL，提取真正的订阅链接
"""

import re
import urllib.parse
from urllib.parse import urlparse, unquote
from typing import List, Set
import logging
import html

class URLExtractor:
    """URL提取和清理器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # 订阅链接的正则表达式模式
        self.subscription_patterns = [
            # 标准格式：https://domain.com/api/v1/client/subscribe?token=xxx
            r'https?://[^\s"\'<>]+api/v1/client/subscribe\?token=[A-Za-z0-9]+',
            # 包含HTML标签的格式
            r'<code>https?://[^\s"\'<>]+api/v1/client/subscribe\?token=[A-Za-z0-9]+</code>',
            # 包含引号的格式
            r'["\']https?://[^\s"\'<>]+api/v1/client/subscribe\?token=[A-Za-z0-9]+["\']',
            # 更宽松的匹配，包含可能的额外参数，但限制在合理范围内
            r'https?://[^\s"\'<>]+api/v1/client/subscribe\?token=[A-Za-z0-9]+(?:&[^=\s"\'<>]*=[^=\s"\'<>]*)*',
            # 专门处理包含flag参数的URL
            r'https?://[^\s"\'<>]+api/v1/client/subscribe\?token=[A-Za-z0-9]+&flag=[A-Za-z0-9]+',
            
            # 新增：其他常见订阅格式
            r'https?://[^\s"\'<>]+/subscribe/link\?token=[A-Za-z0-9]+',
            r'https?://[^\s"\'<>]+/getSubscribe\?token=[A-Za-z0-9]+',
            r'https?://[^\s"\'<>]+/sub\?target=[A-Za-z0-9]+&url=[^\s"\'<>]+',
            r'https?://[^\s"\'<>]+/link/[A-Za-z0-9]+(?:\?[^\s"\'<>]*)?',
            r'https?://[^\s"\'<>]+/s/[A-Za-z0-9]+',
            
            # Base64订阅链接
            r'(?:vmess|vless|trojan|ss|ssr|hysteria2?)://[A-Za-z0-9+/=]+',
            
            # 短链接服务
            r'https?://(?:bit\.ly|goo\.gl|tinyurl\.com|t\.co|short\.link)/[A-Za-z0-9]+',
        ]
        
        # 需要清理的HTML标签和属性
        self.html_cleanup_patterns = [
            r'<[^>]+>',  # 移除所有HTML标签
            r'&[a-zA-Z0-9#]+;',  # 移除HTML实体
            r'%[0-9A-Fa-f]{2}',  # 移除URL编码
        ]
    
    def extract_subscription_urls(self, text: str) -> List[str]:
        """
        从文本中提取所有订阅链接
        
        Args:
            text: 包含订阅链接的文本
            
        Returns:
            List[str]: 提取到的订阅链接列表
        """
        urls = set()
        
        # 使用多种模式匹配
        for pattern in self.subscription_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # 清理HTML标签
                clean_url = self.clean_html_tags(match)
                # 进一步清理和验证
                clean_url = self.clean_and_validate_url(clean_url)
                if clean_url:
                    urls.add(clean_url)
        
        return list(urls)
    
    def clean_html_tags(self, text: str) -> str:
        """
        清理HTML标签和实体
        
        Args:
            text: 包含HTML的文本
            
        Returns:
            str: 清理后的文本
        """
        # 先处理嵌套的HTML实体编码（如 &amp;amp; -> &）
        while '&amp;' in text:
            text = text.replace('&amp;', '&')
        
        # 再使用html.unescape处理其他HTML实体
        text = html.unescape(text)
        
        # 再使用unquote处理URL编码
        text = unquote(text)
        
        # 移除HTML标签
        for pattern in self.html_cleanup_patterns:
            text = re.sub(pattern, '', text)
        
        return text.strip()
    
    def clean_and_validate_url(self, url: str) -> str:
        """
        清理和验证URL
        
        Args:
            url: 原始URL
            
        Returns:
            str: 清理后的有效URL，如果无效则返回None
        """
        try:
            # 移除前后空白字符
            url = url.strip()
            
            # 移除可能的HTML标签残留
            url = re.sub(r'<[^>]*>', '', url)
            
            # 移除可能的引号
            url = url.strip('"\'')
            
            # 检查是否包含必要的部分
            if 'api/v1/client/subscribe?token=' not in url:
                return None
            
            # 使用正则表达式提取纯URL部分，去除后面的额外文本
            # 匹配到第一个中文字符或空格之前，但允许&参数
            url_match = re.match(r'(https?://[^\s"\'<>]+api/v1/client/subscribe\?token=[A-Za-z0-9]+(?:&[^一-龯\s]*)?)', url)
            if url_match:
                url = url_match.group(1)
            else:
                # 如果没有参数，匹配基本URL
                url_match = re.match(r'(https?://[^\s"\'<>]+api/v1/client/subscribe\?token=[A-Za-z0-9]+)', url)
                if url_match:
                    url = url_match.group(1)
            
            # 解析URL
            parsed = urlparse(url)
            
            # 验证URL格式
            if not parsed.scheme or not parsed.netloc:
                return None
            
            # 确保是http或https
            if parsed.scheme not in ['http', 'https']:
                return None
            
            # 重新构建URL，确保格式正确
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                clean_url += f"?{parsed.query}"
            
            return clean_url
            
        except Exception as e:
            self.logger.debug(f"URL清理失败: {url} - {e}")
            return None
    
    def extract_from_search_results(self, search_results: List[dict]) -> List[str]:
        """
        从搜索结果中提取订阅链接
        
        Args:
            search_results: 搜索结果列表
            
        Returns:
            List[str]: 提取到的订阅链接列表
        """
        all_urls = set()
        
        for result in search_results:
            # 从链接字段提取
            link = result.get('link', '')
            if link:
                urls = self.extract_subscription_urls(link)
                all_urls.update(urls)
            
            # 从标题字段提取
            title = result.get('title', '')
            if title:
                urls = self.extract_subscription_urls(title)
                all_urls.update(urls)
            
            # 从摘要字段提取
            snippet = result.get('snippet', '')
            if snippet:
                urls = self.extract_subscription_urls(snippet)
                all_urls.update(urls)
        
        return list(all_urls)
    
    def process_mixed_urls(self, urls: List[str]) -> List[str]:
        """
        处理混合的URL列表（包含真实URL和伪URL）
        
        Args:
            urls: 混合的URL列表
            
        Returns:
            List[str]: 清理后的真实URL列表
        """
        clean_urls = set()
        
        for url in urls:
            # 如果已经是干净的URL，直接添加
            if self.is_clean_url(url):
                clean_urls.add(url)
            else:
                # 尝试提取订阅链接
                extracted = self.extract_subscription_urls(url)
                clean_urls.update(extracted)
        
        return list(clean_urls)
    
    def is_clean_url(self, url: str) -> bool:
        """
        检查URL是否是干净的（不包含HTML标签）
        
        Args:
            url: 要检查的URL
            
        Returns:
            bool: 是否是干净的URL
        """
        # 检查是否包含HTML标签
        if re.search(r'<[^>]+>', url):
            return False
        
        # 检查是否包含HTML实体
        if re.search(r'&[a-zA-Z0-9#]+;', url):
            return False
        
        # 检查是否包含明显的HTML内容
        html_indicators = ['<code>', '</code>', '<br/>', '<div', '</div>', '&lt;', '&gt;']
        for indicator in html_indicators:
            if indicator in url:
                return False
        
        return True

def test_url_extractor():
    """测试URL提取器"""
    print("🧪 测试URL提取器")
    print("=" * 50)
    
    extractor = URLExtractor()
    
    # 测试用例
    test_cases = [
        # 伪URL示例
        'https://t.me/>订阅链接：<code>https://daka778.top/api/v1/client/subscribe?token=1b4d963259351e7719fdb6ce4276cf6d</code><br/>订阅流量：<code>100 GB</code>',
        # 包含引号的URL
        '"https://example.com/api/v1/client/subscribe?token=abc123"',
        # 干净的URL
        'https://daka778.top/api/v1/client/subscribe?token=1b4d963259351e7719fdb6ce4276cf6d',
        # 包含HTML实体的URL
        'https://example.com/api/v1/client/subscribe?token=abc123&amp;flag=clash',
        # 混合内容
        'Some text https://test.com/api/v1/client/subscribe?token=xyz789 more text',
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}:")
        print(f"输入: {test_case[:100]}...")
        
        urls = extractor.extract_subscription_urls(test_case)
        print(f"提取结果: {urls}")
        
        for url in urls:
            is_clean = extractor.is_clean_url(url)
            print(f"  - {url} (干净: {is_clean})")

if __name__ == "__main__":
    test_url_extractor()
