#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版Google API端点搜索器
集成智能密钥管理和钉钉额度通知
"""

import requests
import time
import json
import logging
import re
from datetime import datetime, timedelta
from logger_config import get_scraper_logger
from urllib.parse import urljoin, urlparse, quote_plus
from bs4 import BeautifulSoup
import schedule
import os
import sys
from enhanced_key_manager import EnhancedSerpAPIKeyManager
from url_extractor import URLExtractor
from typing import List, Set, Dict

class EnhancedGoogleAPIScraper:
    def __init__(self, config_file='scraper_config.json'):
        self.config_file = config_file
        self.load_config()
        self.setup_logging()
        # 使用标准API格式搜索
        self.search_query = '"api/v1/client/subscribe?token="'
        
        # 精简地区配置 - 只保留最重要的5个地区
        self.regions = [
            # 中文地区
            {'gl': 'cn', 'hl': 'zh-CN', 'lr': 'lang_zh-CN|lang_en', 'name': '中国大陆'},
            {'gl': 'hk', 'hl': 'zh-HK', 'lr': 'lang_zh-HK|lang_en', 'name': '香港'},
            
            # 英语地区
            {'gl': 'us', 'hl': 'en', 'lr': 'lang_en|lang_zh-CN', 'name': '美国'},
            
            # 亚太地区
            {'gl': 'sg', 'hl': 'en', 'lr': 'lang_en|lang_zh-CN|lang_ms', 'name': '新加坡'},
            {'gl': 'jp', 'hl': 'ja', 'lr': 'lang_ja|lang_en|lang_zh-CN', 'name': '日本'},
        ]
        # 从状态文件加载地区索引，确保轮换状态持久化
        self.region_state_file = 'region_state.json'
        self.current_region_index = self.load_region_index()
        self.results_file = 'api_urls_results.json'
        self.log_file = 'api_scraper.log'
        
        # 初始化增强版SerpAPI密钥管理器
        dingtalk_webhook = "https://oapi.dingtalk.com/robot/send?access_token=afb2baa012da6b3ba990405167b8c1d924e6b489c9013589ab6f6323c4a8509a"
        self.key_manager = EnhancedSerpAPIKeyManager(dingtalk_webhook=dingtalk_webhook)
        
        # 初始化URL提取器
        self.url_extractor = URLExtractor()
        
        
        self.visited_urls_file = 'visited_urls.json'
        self.discovered_urls_file = 'discovered_urls.json'
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Referer': 'https://www.google.com/'
        })
        # 预置同意 Cookie，避免同意页影响
        try:
            from datetime import datetime as _dt, timezone
            consent_val = f"YES+{_dt.now(timezone.utc).strftime('%Y%m%d')}"
            self.session.cookies.set('CONSENT', consent_val, domain='.google.com')
        except Exception:
            pass
        # 在session初始化后设置代理
        self.setup_proxy()
        self.visited_urls = self.load_visited_urls()
        self.discovered_urls = self.load_discovered_urls()
        # 启动时清理重复的已发现URL
        self.cleanup_discovered_urls()
        self.subscription_checker = None
        self.setup_subscription_checker()
        
        # 添加额度监控相关属性
        self.last_quota_notification = None
        self.quota_notification_interval = 6 * 60 * 60  # 6小时发送一次额度通知
        
        # 添加频率限制相关属性
        self.last_serpapi_request = None
        self.last_search_time = None
        self.hourly_request_count = 0
        self.hourly_request_reset_time = None
        
        # 添加钉钉通知频率限制属性
        self.last_dingtalk_notification = None
        self.dingtalk_hourly_count = 0
        self.dingtalk_hourly_reset_time = None
        self.pending_subscription_notifications = []
    
    def load_config(self):
        """加载配置文件"""
        default_config = {
            "proxy": {
                "enabled": False,
                "host": "127.0.0.1",
                "port": 7897,
                "protocol": "http"
            },
            "search": {
                "time_range": "past_12_hours",
                "max_results_per_query": 100,
                "max_pages_to_process": 30
            },
            "validation": {
                "enabled": True,
                "save_only_available": True,
                "send_notifications": True
            },
            "schedule": {
                "interval_hours": 1,
                "immediate_run": True
            },
            "quota_monitoring": {
                "enabled": True,
                "notification_interval_hours": 6,
                "low_quota_threshold": 50
            },
            "rate_limiting": {
                "serpapi_request_delay": 10,
                "min_interval_minutes": 30,
                "max_requests_per_hour": 6
            },
            "dingtalk_notifications": {
                "enabled": True,
                "min_interval_minutes": 10,
                "batch_notifications": True,
                "max_notifications_per_hour": 6,
                "quota_report_interval_hours": 6,
                "subscription_notification_delay": 5
            },
            "regions": {
                "batch_count": 1,  # 每次只搜索1个地区
                "inter_region_delay": 15,
                "priority_regions": ["cn", "hk", "us", "sg", "jp"],
                "use_priority_only": True  # 启用优先地区模式
            }
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                # 合并默认配置
                for key, value in default_config.items():
                    if key not in self.config:
                        self.config[key] = value
                    elif isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            if sub_key not in self.config[key]:
                                self.config[key][sub_key] = sub_value
            except Exception as e:
                print(f"配置文件加载失败，使用默认配置: {e}")
                self.config = default_config
        else:
            self.config = default_config
    
    def load_region_index(self):
        """加载地区索引状态"""
        try:
            if os.path.exists(self.region_state_file):
                with open(self.region_state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    index = data.get('current_region_index', 0)
                    # 确保索引在有效范围内
                    return index % len(self.regions) if index < len(self.regions) else 0
        except Exception as e:
            print(f"加载地区索引状态失败: {e}")
        return 0

    def save_region_index(self):
        """保存地区索引状态"""
        try:
            data = {
                'current_region_index': self.current_region_index,
                'last_update': datetime.now().isoformat()
            }
            with open(self.region_state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存地区索引状态失败: {e}")

    def setup_logging(self):
        """设置日志"""
        daily_logger = get_scraper_logger()
        self.logger = daily_logger.get_logger()
    
    def setup_proxy(self):
        """设置代理（在CI或DISABLE_PROXY=1时禁用）"""
        try:
            if os.getenv('GITHUB_ACTIONS') == 'true' or os.getenv('DISABLE_PROXY') == '1':
                self.logger.info("CI环境或DISABLE_PROXY=1，代理已禁用")
                return
        except Exception:
            pass
        if self.config.get('proxy', {}).get('enabled', False):
            proxy_host = self.config['proxy']['host']
            proxy_port = self.config['proxy']['port']
            proxy_protocol = self.config['proxy']['protocol']
            proxy_url = f"{proxy_protocol}://{proxy_host}:{proxy_port}"
            self.session.proxies.update({'http': proxy_url, 'https': proxy_url})
            self.logger.info(f"已设置代理: {proxy_url}")
    
    def load_visited_urls(self) -> Set[str]:
        """加载已访问的URL"""
        try:
            if os.path.exists(self.visited_urls_file):
                with open(self.visited_urls_file, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
        except Exception as e:
            self.logger.error(f"加载已访问URL失败: {e}")
        return set()
    
    def save_visited_urls(self):
        """保存已访问的URL"""
        try:
            with open(self.visited_urls_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.visited_urls), f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存已访问URL失败: {e}")
    
    def load_discovered_urls(self) -> Set[str]:
        """加载已发现的订阅链接"""
        try:
            if os.path.exists(self.discovered_urls_file):
                with open(self.discovered_urls_file, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
        except Exception as e:
            self.logger.error(f"加载已发现订阅链接失败: {e}")
        return set()
    
    def save_discovered_urls(self):
        """保存已发现的订阅链接"""
        try:
            with open(self.discovered_urls_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.discovered_urls), f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存已发现订阅链接失败: {e}")
    
    def extract_base_subscription_url(self, url: str) -> str:
        """提取订阅URL的基础部分，用于去重比较"""
        # 移除额外的参数和流量信息
        import re
        
        # 移除流量信息等额外文本
        url = re.sub(r'订阅流量：[^&]*', '', url)
        url = re.sub(r'总流量:[^&]*', '', url)
        url = re.sub(r'剩余流量:[^&]*', '', url)
        url = re.sub(r'已上传:[^&]*', '', url)
        url = re.sub(r'已下载:[^&]*', '', url)
        url = re.sub(r'该订阅将于[^&]*', '', url)
        
        # 分离基础URL和参数
        if '?' in url:
            base_part, params = url.split('?', 1)
            # 只保留token参数
            if 'token=' in params:
                token_match = re.search(r'token=([^&]+)', params)
                if token_match:
                    return f"{base_part}?token={token_match.group(1)}"
        
        return url.strip()
    
    def cleanup_discovered_urls(self):
        """清理discovered_urls中的重复项"""
        try:
            # 按基础URL去重
            unique_urls = {}
            for url in self.discovered_urls:
                base_url = self.extract_base_subscription_url(url)
                if base_url not in unique_urls:
                    unique_urls[base_url] = url
            
            # 更新discovered_urls
            old_count = len(self.discovered_urls)
            self.discovered_urls = set(unique_urls.values())
            new_count = len(self.discovered_urls)
            
            if old_count != new_count:
                self.logger.info(f"📝 清理已发现URL: {old_count} -> {new_count} (移除 {old_count - new_count} 个重复项)")
                self.save_discovered_urls()
        except Exception as e:
            self.logger.error(f"清理已发现URL失败: {e}")
    
    def setup_subscription_checker(self):
        """设置订阅检测器"""
        try:
            from subscription_checker import SubscriptionChecker
            self.subscription_checker = SubscriptionChecker(use_proxy=self.config.get('proxy', {}).get('enabled', False))
            self.logger.info("订阅检测器初始化成功")
        except Exception as e:
            self.logger.error(f"订阅检测器初始化失败: {e}")
            self.subscription_checker = None
    
    def check_quota_silently(self):
        """静默检查额度，不发送通知"""
        try:
            # 检查所有密钥额度
            self.logger.info("正在检查密钥额度...")
            quotas = self.key_manager.check_all_quotas(force_refresh=True)
            
            # 检查是否有密钥额度不足
            available_keys = [q for q in quotas if q['success'] and q['account_status'] == 'Active']
            low_quota_threshold = self.config.get('quota_monitoring', {}).get('low_quota_threshold', 50)
            
            low_quota_keys = [q for q in available_keys if q['total_searches_left'] < low_quota_threshold]
            if low_quota_keys:
                self.logger.warning(f"发现 {len(low_quota_keys)} 个密钥额度不足 {low_quota_threshold} 次")
                for key in low_quota_keys:
                    self.logger.warning(f"密钥 {key['api_key'][:10]}... 剩余 {key['total_searches_left']} 次")
            
        except Exception as e:
            self.logger.error(f"检查额度时发生错误: {e}")
    
    def check_quota_and_notify(self):
        """检查额度并发送通知"""
        try:
            # 检查是否应该发送额度通知
            now = datetime.now()
            if (self.last_quota_notification and 
                (now - self.last_quota_notification).seconds < self.quota_notification_interval):
                return
            
            # 检查所有密钥额度
            self.logger.info("正在检查密钥额度...")
            quotas = self.key_manager.check_all_quotas(force_refresh=True)
            
            # 发送钉钉通知
            if self.config.get('quota_monitoring', {}).get('enabled', True):
                success = self.key_manager.send_quota_notification(quotas)
                if success:
                    self.last_quota_notification = now
                    self.logger.info("额度通知发送成功")
                else:
                    self.logger.warning("额度通知发送失败")
            
            # 检查是否有密钥额度不足
            available_keys = [q for q in quotas if q['success'] and q['account_status'] == 'Active']
            low_quota_threshold = self.config.get('quota_monitoring', {}).get('low_quota_threshold', 50)
            
            low_quota_keys = [q for q in available_keys if q['total_searches_left'] < low_quota_threshold]
            if low_quota_keys:
                self.logger.warning(f"发现 {len(low_quota_keys)} 个密钥额度不足 {low_quota_threshold} 次")
                for key in low_quota_keys:
                    self.logger.warning(f"密钥 {key['api_key'][:10]}... 剩余 {key['total_searches_left']} 次")
            
        except Exception as e:
            self.logger.error(f"检查额度时发生错误: {e}")
    
    def send_round_completion_notification_if_needed(self):
        """检查SerpAPI使用量是否达到阈值并发送通知"""
        try:
            self.logger.info("检查SerpAPI使用量是否达到通知阈值...")
            quotas = self.key_manager.check_all_quotas(force_refresh=True)
            if quotas:
                # 只发送SerpAPI使用量阈值通知，不发送轮次结束报告
                self._send_serpapi_usage_threshold_notification(quotas)
            else:
                self.logger.warning("无法获取密钥使用情况信息")
        except Exception as e:
            self.logger.error(f"检查SerpAPI使用量阈值时出错: {e}")
    
    def _send_serpapi_usage_threshold_notification(self, quotas: List[Dict]):
        """
        发送SerpAPI使用量阈值通知（仅在达到阈值时发送）
        
        Args:
            quotas: 密钥配额信息列表
        """
        try:
            self.logger.info("检查SerpAPI使用量是否达到通知阈值...")
            
            # 导入订阅检测器
            from subscription_checker import SubscriptionChecker
            
            # 计算总使用量和配额
            total_used = 0
            total_quota = 0
            
            # 构建详细的密钥信息字典（用于通知显示）
            quotas_detail = {}
            
            for i, quota_info in enumerate(quotas, 1):
                if quota_info and isinstance(quota_info, dict) and quota_info.get('success'):
                    used = quota_info.get('this_month_usage', 0)
                    quota = quota_info.get('searches_per_month', 0)
                    if used is not None and quota and quota > 0:
                        total_used += used
                        total_quota += quota
                        
                        # 添加到详细信息字典中
                        quotas_detail[f"密钥{i}"] = {
                            'searches_used_today': used,
                            'quota_limit': quota
                        }
                    else:
                        # 记录失效的密钥
                        quotas_detail[f"密钥{i}"] = None
            
            if total_used > 0 and total_quota > 0:
                self.logger.debug(f"SerpAPI总使用量: {total_used}/{total_quota}")
                
                # 创建订阅检测器实例并发送阈值通知
                checker = SubscriptionChecker()
                success = checker.send_serpapi_usage_notification(total_used, total_quota, quotas)
                
                if success:
                    self.logger.info("✅ SerpAPI使用量阈值检查完成")
                else:
                    self.logger.warning("❌ SerpAPI使用量阈值通知发送失败")
            else:
                self.logger.debug("无法计算SerpAPI使用量数据")
                
        except Exception as e:
            self.logger.error(f"SerpAPI使用量阈值检查失败: {e}")
    
    def search_google_with_serpapi(self, query: str, time_range: str = "past_12_hours", region: Dict = None) -> List[Dict]:
        """使用SerpAPI搜索Google"""
        try:
            # 获取最优密钥
            api_key = self.key_manager.get_optimal_key()
            if not api_key:
                self.logger.error("没有可用的API密钥")
                return []
            
            # 构建搜索参数
            # 使用动态地区参数以获得不同地区的搜索结果
            if region is None:
                region = {'gl': 'cn', 'hl': 'zh-CN', 'lr': 'lang_zh-CN|lang_en'}  # 默认中国地区
                
            params = {
                'api_key': api_key,
                'engine': 'google',
                'q': query,
                'google_domain': 'google.com',  
                'gl': region['gl'],  # 动态地理位置
                'hl': region['hl'],  # 动态界面语言
                'num': self.config['search']['max_results_per_query'],
                'lr': region.get('lr', 'lang_zh-CN|lang_en'),  # 动态语言限制
            }
            
            # 添加时间范围
            time_mapping = {
                'past_hour': 'qdr:h',
                'past_12_hours': 'qdr:d',
                'past_24_hours': 'qdr:d',
                'past_week': 'qdr:w',
                'past_month': 'qdr:m',
                'past_year': 'qdr:y'
            }
            
            if time_range in time_mapping:
                params['tbs'] = time_mapping[time_range]
            
            # 添加过滤参数
            params['filter'] = '0'  # 不过滤结果
            
            self.logger.info(f"SerpAPI 搜索参数: {params}")
            
            # 发送请求 - 先尝试使用session（带代理），失败时自动切换到直连
            try:
                response = self.session.get('https://serpapi.com/search', params=params, timeout=30)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, 
                    requests.exceptions.ChunkedEncodingError) as e:
                error_str = str(e)
                if ("timed out" in error_str and "Connection to" in error_str) or \
                   "Unable to connect to proxy" in error_str or \
                   "ProxyError" in error_str or \
                   "ConnectTimeoutError" in error_str or \
                   "Connection aborted" in error_str or \
                   "RemoteDisconnected" in error_str:
                    self.logger.info(f"SerpAPI连接问题，切换到直连模式: {e}")
                    response = requests.get('https://serpapi.com/search', params=params, timeout=30)
                else:
                    raise
            
            if response.status_code == 200:
                data = response.json()
                organic_results = data.get('organic_results', [])
                self.logger.info(f"SerpAPI 有机结果 {len(organic_results)} 条")
                return organic_results
            elif response.status_code == 401:
                self.logger.error("SerpAPI认证失败，密钥可能无效")
                self.key_manager.mark_key_failed(api_key)
                return []
            elif response.status_code == 429:
                self.logger.error("SerpAPI请求频率限制")
                self.key_manager.mark_key_failed(api_key)
                return []
            else:
                self.logger.error(f"SerpAPI请求失败: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            self.logger.error(f"SerpAPI搜索异常: {e}")
            return []
    
    def extract_api_urls_from_page(self, url: str) -> List[str]:
        """从网页中提取API URL"""
        try:
            # 检查是否已访问过
            if url in self.visited_urls:
                return []
            
            self.visited_urls.add(url)
            
            # 跳过某些已知难以访问的网站
            skip_domains = ['telemetr.io', 'facebook.com', 'x.com', 'twitter.com']
            if any(domain in url for domain in skip_domains):
                self.logger.info(f"跳过已知难以访问的域名: {url}")
                return []
            
            # 发送请求，增加重试机制
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    # 设置更宽松的headers，模拟浏览器
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                    }
                    
                    response = self.session.get(url, timeout=15, headers=headers, allow_redirects=True)
                    
                    # 对于某些错误状态，不抛出异常，而是继续尝试解析
                    if response.status_code in [200, 301, 302]:
                        break
                    elif response.status_code in [403, 404, 429]:
                        self.logger.warning(f"页面访问受限 {url}, 状态码: {response.status_code}")
                        return []
                    else:
                        response.raise_for_status()
                        
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    # 检查是否是代理连接问题
                    error_str = str(e)
                    if ("timed out" in error_str and "Connection to" in error_str) or \
                       "Unable to connect to proxy" in error_str or \
                       "ProxyError" in error_str or \
                       "ConnectTimeoutError" in error_str:
                        # 代理连接失败，尝试直连
                        try:
                            self.logger.info(f"代理连接失败，尝试直连访问: {url}")
                            direct_session = requests.Session()
                            direct_session.headers.update(headers)
                            response = direct_session.get(url, timeout=15, allow_redirects=True)
                            
                            if response.status_code in [200, 301, 302]:
                                self.logger.info(f"直连访问成功: {url}")
                                break
                            elif response.status_code in [403, 404, 429]:
                                self.logger.warning(f"页面访问受限 {url}, 状态码: {response.status_code}")
                                return []
                            else:
                                response.raise_for_status()
                                
                        except Exception as direct_error:
                            self.logger.warning(f"直连访问也失败 {url}: {direct_error}")
                            if attempt == max_retries - 1:
                                self.logger.warning(f"页面访问彻底失败 {url}: 代理和直连都失败")
                                return []
                            time.sleep(2)
                            continue
                    else:
                        # 其他类型的连接错误
                        if attempt == max_retries - 1:
                            self.logger.warning(f"页面访问超时/连接失败 {url}: {e}")
                            return []
                        time.sleep(2)  # 重试前等待2秒
                        continue
            
            # 解析HTML内容
            try:
                # 尝试不同的编码
                content = response.content
                if response.encoding:
                    content = response.text
                
                soup = BeautifulSoup(content, 'html.parser')
                
                # 获取页面文本内容
                text = soup.get_text()
                
                # 同时也搜索HTML源码中的链接（有些链接可能在注释或script中）
                html_text = str(soup)
                
                # 合并文本内容
                full_text = text + "\n" + html_text
                
                # 使用URL提取器提取订阅链接
                api_urls = self.url_extractor.extract_subscription_urls(full_text)
                
                if api_urls:
                    self.logger.info(f"✅ 从 {url} 提取到 {len(api_urls)} 个订阅链接")
                    for api_url in api_urls:
                        self.logger.info(f"   发现: {api_url}")
                else:
                    self.logger.debug(f"从 {url} 未找到订阅链接")
                
                return api_urls
                
            except Exception as parse_error:
                self.logger.warning(f"解析页面内容失败 {url}: {parse_error}")
                return []
            
        except Exception as e:
            self.logger.error(f"提取 {url} 中的API URL失败: {e}")
            return []
    
    def scrape_api_urls(self) -> List[str]:
        """主要搜索逻辑 - 支持批量多地区搜索"""
        self.logger.info("开始搜索API URL")
        
        # 只检查额度，不发送通知
        self.check_quota_silently()
        
        all_api_urls = []
        time_range = self.config['search']['time_range']
        
        # 每次只搜索一个地区，轮换执行
        inter_region_delay = self.config.get('regions', {}).get('inter_region_delay', 15)
        priority_regions = self.config.get('regions', {}).get('priority_regions', [])
        use_priority_only = self.config.get('regions', {}).get('use_priority_only', False)
        
        # 确定本次要搜索的地区（只选择一个）
        regions_to_search = []
        executed_regions = []  # 记录实际执行的地区信息，用于保存结果
        
        if use_priority_only and priority_regions:
            # 从优先地区中轮换选择
            priority_region_configs = []
            for region_code in priority_regions:
                for region in self.regions:
                    if region['gl'] == region_code:
                        priority_region_configs.append(region)
                        break
            # 只选择当前索引对应的优先地区
            if priority_region_configs:
                region_index = self.current_region_index % len(priority_region_configs)
                regions_to_search = [priority_region_configs[region_index]]
        else:
            # 从所有地区中轮换选择
            total_regions = len(self.regions)
            region_index = self.current_region_index % total_regions
            regions_to_search = [self.regions[region_index]]
        
        try:
            query = self.search_query
            self.logger.info(f"使用搜索查询: {query}")
            self.logger.info(f"本次搜索地区数量: {len(regions_to_search)}")
            
            # 循环搜索各个地区
            for i, current_region in enumerate(regions_to_search):
                self.logger.info(f"[{i+1}/{len(regions_to_search)}] 搜索地区: {current_region['name']} (gl={current_region['gl']}, hl={current_region['hl']}, lr={current_region.get('lr', 'lang_zh-CN|lang_en')})")
                
                try:
                    # 使用SerpAPI搜索当前地区
                    organic_results = self.search_google_with_serpapi(query, time_range, current_region)
                    
                    if not organic_results:
                        self.logger.warning(f"地区 {current_region['name']} 未获取到搜索结果")
                        executed_regions.append(current_region)  # 即使没结果也记录执行过
                        continue
                    
                    # 记录执行的地区
                    executed_regions.append(current_region)
                    
                    # 提取直接命中的完整订阅URL（包括伪URL）
                    direct_urls = []
                    for result in organic_results:
                        # 从链接字段提取
                        link = result.get('link', '')
                        if link:
                            extracted_urls = self.url_extractor.extract_subscription_urls(link)
                            direct_urls.extend(extracted_urls)
                        
                        # 从标题字段提取
                        title = result.get('title', '')
                        if title:
                            extracted_urls = self.url_extractor.extract_subscription_urls(title)
                            direct_urls.extend(extracted_urls)
                        
                        # 从摘要字段提取
                        snippet = result.get('snippet', '')
                        if snippet:
                            extracted_urls = self.url_extractor.extract_subscription_urls(snippet)
                            direct_urls.extend(extracted_urls)
                    
                    # 去重并记录
                    direct_urls = list(set(direct_urls))
                    for url in direct_urls:
                        self.logger.info(f"[{current_region['name']}] 直接命中完整订阅URL: {url}")
                    
                    # 立即验证直接命中的订阅链接（智能去重）
                    for url in direct_urls:
                        # 提取URL基础部分用于去重检查
                        base_url = self.extract_base_subscription_url(url)
                        
                        # 检查是否已经验证过这个基础URL  
                        already_discovered = any(
                            self.extract_base_subscription_url(discovered_url) == base_url 
                            for discovered_url in self.discovered_urls
                        )
                        
                        if already_discovered:
                            self.logger.info(f"⏭️ [{current_region['name']}] 跳过已验证的订阅链接: {url}")
                            continue
                        
                        # 双重检查：确保基础URL不重复
                        if base_url in {self.extract_base_subscription_url(u) for u in self.discovered_urls}:
                            self.logger.debug(f"⚠️ [{current_region['name']}] 基础URL已存在，跳过: {base_url}")
                            continue
                            
                        self.discovered_urls.add(url)  # 添加到已发现列表
                        if self.subscription_checker:
                            self.logger.info(f"🔍 [{current_region['name']}] 验证新发现的订阅链接: {url}")
                            result = self.subscription_checker.check_subscription_url(url)
                            if result['available']:
                                self.logger.info(f"✅ [{current_region['name']}] 直接命中的订阅链接可用: {url}")
                            else:
                                self.logger.info(f"❌ [{current_region['name']}] 直接命中的订阅链接不可用: {url}")
                    
                    all_api_urls.extend(direct_urls)
                    
                    # 处理需要访问的页面
                    pages_to_process = organic_results[:self.config['search']['max_pages_to_process']]
                    for result in pages_to_process:
                        link = result.get('link', '')
                        if link and 'api/v1/client/subscribe?token=' not in link:
                            page_urls = self.extract_api_urls_from_page(link)
                            for url in page_urls:
                                # 提取URL基础部分用于去重检查
                                base_url = self.extract_base_subscription_url(url)
                                
                                # 检查是否已经验证过这个基础URL
                                already_discovered = any(
                                    self.extract_base_subscription_url(discovered_url) == base_url 
                                    for discovered_url in self.discovered_urls
                                )
                                
                                if not already_discovered:
                                    # 双重检查：确保基础URL不重复  
                                    if base_url not in {self.extract_base_subscription_url(u) for u in self.discovered_urls}:
                                        self.discovered_urls.add(url)
                                        if self.subscription_checker:
                                            self.logger.info(f"🔍 [{current_region['name']}] 验证页面发现的订阅链接: {url}")
                                            result = self.subscription_checker.check_subscription_url(url)
                                            if result['available']:
                                                self.logger.info(f"✅ [{current_region['name']}] 发现的订阅链接可用: {url}")
                                            else:
                                                self.logger.info(f"❌ [{current_region['name']}] 发现的订阅链接不可用: {url}")
                                else:
                                    self.logger.info(f"⏭️ [{current_region['name']}] 跳过已验证的页面订阅链接: {url}")
                            all_api_urls.extend(page_urls)
                    
                    self.logger.info(f"[{current_region['name']}] 地区搜索完成，发现 {len(direct_urls)} 个URL")
                    
                except Exception as region_error:
                    self.logger.error(f"地区 {current_region['name']} 搜索失败: {region_error}")
                    # 即使失败也记录执行过的地区
                    executed_regions.append(current_region)
                
                # 由于只搜索一个地区，不需要地区间延迟
            
            # 更新地区索引（每次推进1个位置）
            if not use_priority_only:
                self.current_region_index = (self.current_region_index + 1) % len(self.regions)
                self.save_region_index()  # 保存地区索引状态
            else:
                # 如果是优先地区模式，也要更新索引
                self.current_region_index = (self.current_region_index + 1) % len(priority_regions)
                self.save_region_index()
            
            # 保存执行的地区列表，供结果保存时使用
            self.last_executed_regions = executed_regions
            
            # 保存状态
            self.save_visited_urls()
            self.save_discovered_urls()
            
            self.logger.info(f"批量搜索完成，共搜索 {len(executed_regions)} 个地区，找到 {len(all_api_urls)} 个API URL")
            return all_api_urls
            
        except Exception as e:
            self.logger.error(f"批量搜索过程中发生错误: {e}")
            return []
    
    def save_results(self, api_urls: List[str]):
        """保存搜索结果 - 支持批量地区信息"""
        try:
            # 获取执行的地区信息
            executed_regions = getattr(self, 'last_executed_regions', [])
            
            # 最终去重处理（使用基础URL去重）
            unique_urls = {}
            for url in api_urls:
                base_url = self.extract_base_subscription_url(url)
                if base_url not in unique_urls:
                    unique_urls[base_url] = url
            
            # 转换为去重后的列表
            deduplicated_urls = list(unique_urls.values())
            original_count = len(api_urls)
            deduplicated_count = len(deduplicated_urls)
            
            if original_count != deduplicated_count:
                self.logger.info(f"🔄 最终去重: {original_count} -> {deduplicated_count} (移除 {original_count - deduplicated_count} 个重复URL)")
            
            if executed_regions:
                # 构建地区信息列表
                regions_info = []
                for region in executed_regions:
                    region_str = f"{region['name']} (gl={region['gl']}, hl={region['hl']}, lr={region.get('lr', 'lang_zh-CN|lang_en')})"
                    regions_info.append(region_str)
                
                # 构建地区摘要
                if len(executed_regions) == 1:
                    regions_summary = regions_info[0]
                else:
                    regions_summary = f"批量搜索 {len(executed_regions)} 个地区: " + ", ".join([r['name'] for r in executed_regions])
            else:
                # 回退到单地区模式
                current_region = self.regions[(self.current_region_index - 1) % len(self.regions)]
                regions_info = [f"{current_region['name']} (gl={current_region['gl']}, hl={current_region['hl']}, lr={current_region.get('lr', 'lang_zh-CN|lang_en')})"]
                regions_summary = regions_info[0]
            
            # 保存到JSON文件
            result_data = {
                'timestamp': datetime.now().isoformat(),
                'query': self.search_query,
                'search_type': 'batch_regions' if len(executed_regions) > 1 else 'single_region',
                'regions_summary': regions_summary,
                'regions_detail': regions_info,
                'regions_count': len(executed_regions) if executed_regions else 1,
                'total_urls': deduplicated_count,
                'original_urls': original_count,
                'urls': deduplicated_urls
            }
            
            with open(self.results_file, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            
            # 保存到文本文件
            with open('api_urls.txt', 'w', encoding='utf-8') as f:
                for url in deduplicated_urls:
                    f.write(url + '\n')
            
            self.logger.info(f"结果已保存到 {self.results_file} 和 api_urls.txt")
            self.logger.info(f"搜索模式: {result_data['search_type']}, 地区: {regions_summary}")
            
        except Exception as e:
            self.logger.error(f"保存结果失败: {e}")
    
    def run_scraping_task(self):
        """执行搜索任务"""
        self.logger.info("=" * 50)
        self.logger.info("开始执行搜索任务")
        self.logger.info("=" * 50)
        
        try:
            # 执行搜索
            api_urls = self.scrape_api_urls()
            
            if api_urls:
                # 保存结果
                self.save_results(api_urls)
                self.logger.info(f"任务完成，找到 {len(api_urls)} 个API URL")
            else:
                self.logger.info("任务完成，未找到新的API URL")
            
            # 任务完成后检查SerpAPI使用量阈值
            self.send_round_completion_notification_if_needed()
                
        except Exception as e:
            self.logger.error(f"执行搜索任务时发生错误: {e}")
    
    def start_scheduler(self):
        """启动定时任务调度器"""
        interval_hours = self.config['schedule']['interval_hours']
        
        # 设置定时任务
        schedule.every(interval_hours).hours.do(self.run_scraping_task)
        
        # 如果配置了立即运行
        if self.config['schedule']['immediate_run']:
            self.logger.info("立即执行一次搜索任务")
            self.run_scraping_task()
        
        self.logger.info(f"定时任务已启动，每 {interval_hours} 小时执行一次")
        
        # 运行调度器
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
        except KeyboardInterrupt:
            self.logger.info("收到中断信号，正在停止...")
        except Exception as e:
            self.logger.error(f"调度器运行异常: {e}")

def main():
    """主函数"""
    print("🚀 启动增强版Google API搜索器")
    print("=" * 50)
    
    try:
        scraper = EnhancedGoogleAPIScraper()
        scraper.start_scheduler()
    except Exception as e:
        print(f"启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
