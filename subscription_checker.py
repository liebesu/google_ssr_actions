#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订阅链接可用性检测脚本
功能：检测订阅链接是否可用，可用时发送钉钉通知
"""

import requests
import json
import time
import logging
import urllib3
import os
import re
from urllib.parse import urlparse
from typing import Dict, List, Optional
from logger_config import get_subscription_logger

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置
DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=afb2baa012da6b3ba990405167b8c1d924e6b489c9013589ab6f6323c4a8509a"
DINGTALK_KEYWORD = ":"  # 钉钉关键字
REQUEST_TIMEOUT = 10  # 请求超时时间（秒）
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# 代理配置
PROXY_CONFIG = {
    'http': 'http://192.168.100.110:7893',
    'https': 'http://192.168.100.110:7893'
}

# 使用新的日志系统
daily_logger = get_subscription_logger()
logger = daily_logger.get_logger()


class SubscriptionChecker:
    """订阅链接检测器"""
    
    def __init__(self, use_proxy=True):
        self.session = requests.Session()
        self.use_proxy = use_proxy
        
        # 设置请求头
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        
        # 设置代理
        if self.use_proxy:
            # 测试代理连接
            if self._test_proxy_connection():
                self.session.proxies.update(PROXY_CONFIG)
                logger.info(f"已启用代理: {PROXY_CONFIG}")
                self.proxy_available = True
            else:
                logger.warning("代理连接失败，切换到直连模式")
                self.use_proxy = False
                self.proxy_available = False
        else:
            logger.info("未使用代理")
            self.proxy_available = False
        
        # 已发送钉钉通知的URL记录文件
        self.notified_urls_file = 'notified_urls.txt'
        self.notified_urls = self._load_notified_urls()
        
        # 钉钉Webhook配置
        self.dingtalk_webhook = DINGTALK_WEBHOOK
    
    def _test_proxy_connection(self) -> bool:
        """
        测试代理连接是否可用
        
        Returns:
            bool: 代理是否可用
        """
        try:
            # 创建临时session测试代理
            test_session = requests.Session()
            test_session.proxies.update(PROXY_CONFIG)
            test_session.headers.update({'User-Agent': USER_AGENT})
            
            # 测试连接到一个简单的HTTP服务
            response = test_session.get('http://httpbin.org/ip', timeout=5)
            if response.status_code == 200:
                logger.info(f"代理测试成功: {response.json().get('origin', 'Unknown IP')}")
                return True
            else:
                logger.warning(f"代理测试失败，状态码: {response.status_code}")
                return False
                
        except Exception as e:
            logger.warning(f"代理测试异常: {e}")
            return False
    
    def _load_notified_urls(self) -> set:
        """
        从文件加载已通知的URL列表
        
        Returns:
            set: 已通知的URL集合
        """
        try:
            if os.path.exists(self.notified_urls_file):
                with open(self.notified_urls_file, 'r', encoding='utf-8') as f:
                    urls = set(line.strip() for line in f if line.strip())
                logger.info(f"加载了 {len(urls)} 个已通知URL记录")
                return urls
            else:
                logger.info("未找到已通知URL记录文件，创建新的记录")
                return set()
        except Exception as e:
            logger.error(f"加载已通知URL记录失败: {e}")
            return set()
    
    def _save_notified_urls(self):
        """
        保存已通知的URL列表到文件
        """
        try:
            with open(self.notified_urls_file, 'w', encoding='utf-8') as f:
                for url in sorted(self.notified_urls):
                    f.write(f"{url}\n")
            logger.debug(f"保存了 {len(self.notified_urls)} 个已通知URL记录")
        except Exception as e:
            logger.error(f"保存已通知URL记录失败: {e}")
    
    def _calculate_next_reset_date(self, quota_info: Dict, key_index: int) -> str:
        """
        计算SerpAPI账户的下次重置时间
        
        Args:
            quota_info: 配额信息字典
            key_index: 密钥索引
            
        Returns:
            str: 下次重置时间字符串
        """
        try:
            from datetime import datetime, timedelta
            import calendar
            import json
            import os
            
            # 获取当前时间
            now = datetime.now()
            
            # 尝试从配置文件加载注册日期
            registration_dates_file = 'api_key_registration_dates.json'
            registration_dates = {}
            
            if os.path.exists(registration_dates_file):
                try:
                    with open(registration_dates_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        registration_dates = data.get('key_registration_dates', {})
                except Exception as e:
                    logger.warning(f"加载注册日期配置文件失败: {e}")
            
            # 获取当前API密钥
            current_api_key = quota_info.get('api_key', '')
            
            # 查找对应的注册日期
            registration_date_str = None
            for key, date in registration_dates.items():
                if key in current_api_key or current_api_key in key:
                    registration_date_str = date
                    break
            
            if registration_date_str:
                try:
                    # 解析注册日期
                    registration_date = datetime.strptime(registration_date_str, '%Y-%m-%d')
                    
                    # 计算下次重置时间（基于注册日期的每月对应日）
                    if now.month == 12:
                        # 如果当前是12月，重置时间是下年同月同日
                        next_reset = registration_date.replace(year=now.year + 1)
                    else:
                        # 否则是下个月同月同日
                        next_reset = registration_date.replace(year=now.year, month=now.month + 1)
                    
                    # 如果计算出的重置时间已经过了，则使用下下个月
                    if next_reset <= now:
                        if now.month == 11:
                            next_reset = registration_date.replace(year=now.year + 1, month=1)
                        elif now.month == 12:
                            next_reset = registration_date.replace(year=now.year + 1, month=2)
                        else:
                            next_reset = registration_date.replace(year=now.year, month=now.month + 2)
                    
                    # 确保日期有效（处理2月29日等特殊情况）
                    last_day_of_month = calendar.monthrange(next_reset.year, next_reset.month)[1]
                    if next_reset.day > last_day_of_month:
                        next_reset = next_reset.replace(day=last_day_of_month)
                    
                    logger.debug(f"密钥 {key_index} 基于注册日期 {registration_date_str} 计算重置时间: {next_reset.strftime('%Y-%m-%d')}")
                    return next_reset.strftime("%Y-%m-%d")
                    
                except ValueError as e:
                    logger.warning(f"解析注册日期失败: {registration_date_str}, 错误: {e}")
            
            # 如果没有找到注册日期，使用默认逻辑（基于密钥索引）
            logger.debug(f"密钥 {key_index} 未找到注册日期，使用默认计算方式")
            
            # 使用密钥索引作为偏移量，确保不同密钥有不同的重置时间
            offset_days = (key_index - 1) * 7  # 每个密钥相差7天，避免过于接近
            
            # 计算下个月的同一天作为重置时间
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.replace(month=now.month + 1, day=1)
            
            # 添加偏移量
            reset_date = next_month + timedelta(days=offset_days)
            
            # 确保日期不超过下个月的最后一天
            last_day_of_month = calendar.monthrange(reset_date.year, reset_date.month)[1]
            if reset_date.day > last_day_of_month:
                reset_date = reset_date.replace(day=last_day_of_month)
            
            return reset_date.strftime("%Y-%m-%d")
            
        except Exception as e:
            logger.warning(f"计算重置时间失败: {e}")
            # 如果计算失败，返回下个月1号作为默认值
            from datetime import datetime
            now = datetime.now()
            if now.month == 12:
                return f"{now.year + 1}-01-01"
            else:
                return f"{now.year}-{now.month + 1:02d}-01"
    
    def normalize_url(self, url: str) -> str:
        """
        标准化URL，用于去重比较
        
        Args:
            url: 原始URL
            
        Returns:
            str: 标准化后的URL
        """
        try:
            # 去除首尾空白字符
            normalized = url.strip()
            
            # 去除开头的特殊符号
            while normalized and normalized[0] in '-_*+~`!@#$%^&()[]{}|\\:;"\'<>,.?/':
                normalized = normalized[1:]
            
            # 去除结尾的特殊符号
            while normalized and normalized[-1] in '-_*+~`!@#$%^&()[]{}|\\:;"\'<>,.?/':
                normalized = normalized[:-1]
            
            # 去除多余的空格
            normalized = ' '.join(normalized.split())
            
            # 如果没有协议，添加https://
            if not normalized.startswith(('http://', 'https://')):
                if normalized.startswith('//'):
                    normalized = 'https:' + normalized
                else:
                    normalized = 'https://' + normalized
            
            # 解析URL并重新构建
            parsed = urlparse(normalized)
            
            # 重建URL，保留必要的部分
            if 'api/v1/client/subscribe' in parsed.path:
                # 对于订阅API，保留完整URL包括token参数
                # 只移除clash标志等非必要参数
                if '&flag=clash' in normalized:
                    normalized = normalized.replace('&flag=clash', '')
                if '?flag=clash' in normalized:
                    normalized = normalized.replace('?flag=clash', '')
                # 保持原始URL不变，因为token是必需的
            else:
                # 对于其他URL，保留完整路径但去除查询参数
                normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            
            return normalized.lower()  # 转换为小写以便比较
            
        except Exception as e:
            logger.warning(f"URL标准化失败: {e}")
            return url.strip().lower()
    
    def remove_duplicate_urls(self, urls: List[str]) -> tuple[List[str], Dict[str, List[int]]]:
        """
        去除重复的订阅链接
        
        Args:
            urls: 原始URL列表
            
        Returns:
            tuple: (去重后的URL列表, 重复URL的索引映射)
        """
        normalized_to_indices = {}
        unique_urls = []
        duplicate_mapping = {}
        
        logger.info("开始检测重复的订阅链接...")
        
        for i, url in enumerate(urls):
            if not url.strip():
                continue
                
            normalized = self.normalize_url(url.strip())
            
            if normalized in normalized_to_indices:
                # 发现重复URL
                original_index = normalized_to_indices[normalized]
                if normalized not in duplicate_mapping:
                    duplicate_mapping[normalized] = [original_index]
                duplicate_mapping[normalized].append(i)
                
                logger.info(f"发现重复URL (索引 {i}): {url}")
                logger.info(f"  与索引 {original_index} 的URL重复: {urls[original_index]}")
            else:
                # 新的唯一URL
                normalized_to_indices[normalized] = i
                unique_urls.append(url.strip())
        
        # 统计重复情况
        total_duplicates = sum(len(indices) - 1 for indices in duplicate_mapping.values())
        logger.info(f"去重完成: 原始 {len(urls)} 个URL，去重后 {len(unique_urls)} 个，发现 {total_duplicates} 个重复")
        
        return unique_urls, duplicate_mapping
    
    def print_duplicate_analysis(self, urls: List[str], duplicate_mapping: Dict[str, List[int]]):
        """
        打印重复URL分析结果
        
        Args:
            urls: 原始URL列表
            duplicate_mapping: 重复URL映射
        """
        if not duplicate_mapping:
            print("✅ 未发现重复的订阅链接")
            return
        
        print("\n" + "=" * 60)
        print("重复订阅链接分析")
        print("=" * 60)
        
        for normalized_url, indices in duplicate_mapping.items():
            print(f"\n🔍 重复组 (共 {len(indices)} 个):")
            for i, index in enumerate(indices):
                status_icon = "📌" if i == 0 else "🔄"
                print(f"  {status_icon} 索引 {index}: {urls[index]}")
            
            # 显示标准化后的URL
            print(f"  标准化URL: {normalized_url}")
        
        print(f"\n📊 重复统计:")
        print(f"  总重复组数: {len(duplicate_mapping)}")
        total_duplicates = sum(len(indices) - 1 for indices in duplicate_mapping.values())
        print(f"  总重复URL数: {total_duplicates}")
        print(f"  原始URL数: {len(urls)}")
        print(f"  去重后URL数: {len(urls) - total_duplicates}")
        print("=" * 60)
    
    def test_proxy(self) -> Dict:
        """
        测试代理连接
        
        Returns:
            Dict: 代理测试结果
        """
        test_result = {
            'proxy_enabled': self.use_proxy,
            'proxy_config': PROXY_CONFIG if self.use_proxy else None,
            'test_urls': [],
            'overall_status': 'unknown'
        }
        
        if not self.use_proxy:
            test_result['overall_status'] = 'no_proxy'
            return test_result
        
        # 测试URL列表
        test_urls = [
            'http://httpbin.org/ip',
            'https://httpbin.org/ip',
            'http://ip-api.com/json',
            'https://api.ipify.org?format=json'
        ]
        
        logger.info("开始测试代理连接...")
        
        for url in test_urls:
            try:
                start_time = time.time()
                response = self.session.get(url, timeout=10, verify=False)
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    # 尝试解析响应内容
                    try:
                        ip_info = response.json()
                        if 'origin' in ip_info:
                            ip = ip_info['origin']
                        elif 'query' in ip_info:
                            ip = ip_info['query']
                        elif 'ip' in ip_info:
                            ip = ip_info['ip']
                        else:
                            ip = "未知"
                    except:
                        ip = "解析失败"
                    
                    test_result['test_urls'].append({
                        'url': url,
                        'status': 'success',
                        'response_time': round(response_time, 2),
                        'status_code': response.status_code,
                        'ip_address': ip,
                        'error': None
                    })
                    logger.info(f"代理测试成功: {url} -> IP: {ip}")
                else:
                    test_result['test_urls'].append({
                        'url': url,
                        'status': 'http_error',
                        'response_time': round(response_time, 2),
                        'status_code': response.status_code,
                        'ip_address': None,
                        'error': f"HTTP {response.status_code}"
                    })
                    logger.warning(f"代理测试HTTP错误: {url}, 状态码: {response.status_code}")
                    
            except Exception as e:
                test_result['test_urls'].append({
                    'url': url,
                    'status': 'error',
                    'response_time': 0,
                    'status_code': 0,
                    'ip_address': None,
                    'error': str(e)
                })
                logger.error(f"代理测试失败: {url}, 错误: {e}")
        
        # 判断整体状态
        success_count = sum(1 for t in test_result['test_urls'] if t['status'] == 'success')
        if success_count == 0:
            test_result['overall_status'] = 'failed'
        elif success_count == len(test_urls):
            test_result['overall_status'] = 'success'
        else:
            test_result['overall_status'] = 'partial'
        
        return test_result
    
    def print_proxy_test_result(self, test_result: Dict):
        """打印代理测试结果"""
        print("\n" + "=" * 60)
        print("代理连接测试结果")
        print("=" * 60)
        
        if test_result['proxy_enabled']:
            print(f"代理状态: {'✅ 已启用' if test_result['overall_status'] != 'failed' else '❌ 连接失败'}")
            print(f"代理配置: {test_result['proxy_config']}")
            print(f"整体状态: {test_result['overall_status']}")
            
            print(f"\n详细测试结果:")
            for i, test in enumerate(test_result['test_urls'], 1):
                status_icon = "✅" if test['status'] == 'success' else "❌"
                print(f"{i}. {status_icon} {test['url']}")
                print(f"   状态: {test['status']}")
                print(f"   响应时间: {test['response_time']}秒")
                print(f"   状态码: {test['status_code']}")
                
                if test['ip_address']:
                    print(f"   检测到的IP: {test['ip_address']}")
                
                if test['error']:
                    print(f"   错误: {test['error']}")
                print()
        else:
            print("代理状态: 未启用")
        
        print("=" * 60)
    
    def clean_and_validate_url(self, url: str) -> tuple[bool, str, str]:
        """
        清理和验证URL格式，并自动添加Clash格式标识
        
        Args:
            url: 原始URL字符串
            
        Returns:
            tuple: (是否有效, 清理后的URL, 错误信息)
        """
        # 去除首尾空白字符
        cleaned_url = url.strip()
        
        # 去除开头的特殊符号
        while cleaned_url and cleaned_url[0] in '-_*+~`!@#$%^&()[]{}|\\:;"\'<>,.?/':
            cleaned_url = cleaned_url[1:]
        
        # 去除结尾的特殊符号
        while cleaned_url and cleaned_url[-1] in '-_*+~`!@#$%^&()[]{}|\\:;"\'<>,.?/':
            cleaned_url = cleaned_url[:-1]
        
        # 去除多余的空格
        cleaned_url = ' '.join(cleaned_url.split())
        
        # 如果清理后为空，返回错误
        if not cleaned_url:
            return False, "", "URL为空或只包含特殊符号"
        
        # 检查是否为Clash订阅链接，如果是则自动添加&flag=clash
        if 'api/v1/client/subscribe' in cleaned_url:
            if '&flag=clash' not in cleaned_url:
                # 根据URL是否已有参数来决定添加方式
                if '?' in cleaned_url:
                    cleaned_url += '&flag=clash'
                else:
                    cleaned_url += '?flag=clash'
                logger.info(f"检测到Clash订阅链接，已自动添加&flag=clash: {cleaned_url}")
        
        # 验证URL格式
        parsed_url = urlparse(cleaned_url)
        
        # 如果没有协议，尝试添加https://
        if not parsed_url.scheme:
            if not cleaned_url.startswith('//'):
                cleaned_url = 'https://' + cleaned_url
            else:
                cleaned_url = 'https:' + cleaned_url
            parsed_url = urlparse(cleaned_url)
        
        # 检查是否有域名
        if not parsed_url.netloc:
            return False, cleaned_url, "无效的URL格式：缺少域名"
        
        # 检查协议是否支持
        if parsed_url.scheme not in ['http', 'https']:
            return False, cleaned_url, f"不支持的协议：{parsed_url.scheme}"
        
        return True, cleaned_url, ""
    
    def check_subscription_url(self, url: str) -> Dict:
        """
        检测订阅链接的可用性
        
        Args:
            url: 订阅链接URL
            
        Returns:
            Dict: 包含检测结果的字典
        """
        result = {
            'url': url,
            'status': 'unknown',
            'available': False,
            'response_time': 0,
            'status_code': 0,
            'content_length': 0,
            'error': None,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'cleaned_url': url,
            'node_analysis': {},
            'traffic_info': {},
            'proxy_used': self.use_proxy
        }
        
        try:
            logger.info(f"正在检测订阅链接: {url}")
            
            # 清理和验证URL格式
            is_valid, cleaned_url, error_msg = self.clean_and_validate_url(url)
            if not is_valid:
                result['error'] = error_msg
                result['status'] = 'invalid_url'
                return result
            
            # 更新清理后的URL
            result['cleaned_url'] = cleaned_url
            logger.info(f"URL已清理: {cleaned_url}")
            
            # 验证URL格式
            parsed_url = urlparse(cleaned_url)
            if not parsed_url.scheme or not parsed_url.netloc:
                result['error'] = "无效的URL格式"
                result['status'] = 'invalid_url'
                return result
            
            # 发送请求
            start_time = time.time()
            response = self.session.get(
                cleaned_url, 
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
                verify=False  # 忽略SSL证书验证
            )
            response_time = time.time() - start_time
            
            result['response_time'] = round(response_time, 2)
            result['status_code'] = response.status_code
            result['content_length'] = len(response.content)
            
            # 判断响应状态
            if response.status_code == 200:
                # 检查内容是否有效
                if self._is_valid_subscription_content(response.content):
                    result['status'] = 'available'
                    result['available'] = True
                    logger.info(f"订阅链接可用: {url}")
                    
                    # 使用双重分析方法：传递原始URL，而不是带clash标志的URL
                    original_clean_url = url.replace('&flag=clash', '').replace('?flag=clash', '')
                    analysis_result = self._dual_analyze_subscription(original_clean_url, response.content)
                    result['node_analysis'] = analysis_result
                    result['traffic_info'] = analysis_result.get('traffic_info', {})
                    
                    logger.info(f"节点分析结果: {analysis_result['total_nodes']} 个节点")
                    
                    # 记录流量信息到日志
                    traffic_info = analysis_result.get('traffic_info', {})
                    if traffic_info.get('total_traffic'):
                        logger.info(f"总流量: {traffic_info['total_traffic']} {traffic_info['traffic_unit']}")
                    if traffic_info.get('used_traffic'):
                        logger.info(f"已用流量: {traffic_info['used_traffic']} {traffic_info['traffic_unit']}")
                    if traffic_info.get('remaining_traffic'):
                        logger.info(f"剩余流量: {traffic_info['remaining_traffic']} {traffic_info['traffic_unit']}")
                    if traffic_info.get('expire_date'):
                        logger.info(f"过期时间: {traffic_info['expire_date']}")
                    
                    # 发送钉钉通知
                    logger.info(f"发送钉钉通知: {url}")
                    notification_success = self.send_dingtalk_notification(result)
                    if notification_success:
                        logger.info("✅ 钉钉通知发送成功")
                    else:
                        logger.warning("❌ 钉钉通知发送失败")
                else:
                    result['status'] = 'invalid_content'
                    result['error'] = "响应内容无效"
                    logger.warning(f"订阅链接内容无效: {url}")
            else:
                result['status'] = 'http_error'
                result['error'] = f"HTTP状态码: {response.status_code}"
                logger.warning(f"订阅链接HTTP错误: {url}, 状态码: {response.status_code}")
                
        except requests.exceptions.Timeout:
            result['status'] = 'timeout'
            result['error'] = "请求超时"
            logger.error(f"订阅链接请求超时: {url}")
        except requests.exceptions.ConnectionError:
            result['status'] = 'connection_error'
            result['error'] = "连接错误"
            logger.error(f"订阅链接连接错误: {url}")
        except requests.exceptions.RequestException as e:
            result['status'] = 'request_error'
            result['error'] = str(e)
            logger.error(f"订阅链接请求错误: {url}, 错误: {e}")
        except Exception as e:
            result['status'] = 'unknown_error'
            result['error'] = str(e)
            logger.error(f"订阅链接检测未知错误: {url}, 错误: {e}")
        
        return result
    
    def _is_valid_subscription_content(self, content: bytes) -> bool:
        """
        判断订阅内容是否有效
        
        Args:
            content: 响应内容
            
        Returns:
            bool: 内容是否有效
        """
        try:
            # 转换为字符串
            content_str = content.decode('utf-8', errors='ignore')
            
            # 添加调试信息
            logger.debug(f"内容长度: {len(content_str)}")
            logger.debug(f"内容预览: {content_str[:200]}...")
            
            # 检查是否包含常见的订阅格式标识
            valid_indicators = [
                'vmess://', 'vless://', 'trojan://', 'ss://', 'ssr://',
                'http://', 'https://', 'socks5://',
                'server=', 'port=', 'password=',
                'vmess', 'vless', 'trojan', 'shadowsocks'
            ]
            
            # 检查是否包含有效内容（放宽要求）
            if len(content_str.strip()) < 5:
                logger.debug("内容长度不足5字符")
                return False
            
            # 检查是否包含订阅格式标识
            has_valid_format = any(indicator in content_str.lower() for indicator in valid_indicators)
            logger.debug(f"包含有效格式标识: {has_valid_format}")
            
            # 检查是否包含明显的错误信息
            error_indicators = [
                'error', 'not found', '404', '403', '500', '502', '503',
                'access denied', 'forbidden', 'unauthorized'
            ]
            has_error = any(error in content_str.lower() for error in error_indicators)
            logger.debug(f"包含错误信息: {has_error}")
            
            # 如果内容长度足够且没有错误信息，就认为是有效的
            # 放宽格式要求，因为有些订阅可能使用自定义格式
            if len(content_str.strip()) > 10 and not has_error:
                logger.debug("内容长度足够且无错误信息，认为有效")
                return True
            
            result = has_valid_format and not has_error
            logger.debug(f"最终验证结果: {result}")
            return result
            
        except Exception as e:
            logger.warning(f"内容验证失败: {e}")
            return False
    
    def _try_base64_decode(self, content: str) -> Optional[str]:
        """
        尝试Base64解码内容
        
        Args:
            content: 原始内容字符串
            
        Returns:
            Optional[str]: 解码后的内容，如果解码失败返回None
        """
        try:
            import base64
            
            # 去除所有空白字符和换行符
            cleaned_content = content.replace('\n', '').replace('\r', '').replace(' ', '').replace('\t', '').strip()
            
            # 检查是否可能是Base64编码
            if not self._looks_like_base64(content):
                logger.debug("内容看起来不像Base64编码")
                return None
            
            # 尝试解码
            decoded_bytes = base64.b64decode(cleaned_content)
            decoded_str = decoded_bytes.decode('utf-8', errors='ignore')
            
            logger.debug(f"Base64解码成功，原始长度: {len(cleaned_content)}, 解码后长度: {len(decoded_str)}")
            return decoded_str
            
        except Exception as e:
            logger.debug(f"Base64解码失败: {e}")
            return None
    
    def _looks_like_base64(self, content: str) -> bool:
        """
        判断内容是否看起来像Base64编码
        
        Args:
            content: 内容字符串
            
        Returns:
            bool: 是否像Base64编码
        """
        if not content:
            return False
        
        # 去除空白字符后再检查
        cleaned = content.replace('\n', '').replace('\r', '').replace(' ', '').replace('\t', '')
        
        if len(cleaned) < 20:  # 太短可能不是Base64
            return False
        
        # Base64编码通常包含字母、数字、+、/、=
        valid_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')
        content_chars = set(cleaned)
        
        # 检查是否包含无效字符（允许少量无效字符，可能是换行等）
        invalid_chars = content_chars - valid_chars
        if len(invalid_chars) > 0 and len(invalid_chars) / len(content_chars) > 0.1:
            return False
        
        # 检查Base64特征：大部分字符应该是字母数字
        alphanumeric_count = sum(1 for c in cleaned if c.isalnum())
        if alphanumeric_count / len(cleaned) < 0.6:
            return False
        
        return True
    
    def _is_valid_node_line(self, line: str) -> bool:
        """
        判断一行是否包含有效的节点信息
        
        Args:
            line: 行内容
            
        Returns:
            bool: 是否包含有效节点信息
        """
        if not line or line.startswith('#'):
            return False
        
        # 检查是否包含常见的节点配置参数
        node_indicators = [
            'server=', 'port=', 'password=', 'method=', 'protocol=',
            'obfs=', 'obfs_param=', 'remarks=', 'group=',
            'name=', 'type=', 'uuid=', 'path=', 'host='
        ]
        
        # 如果包含多个节点指示符，认为是有效的节点行
        indicator_count = sum(1 for indicator in node_indicators if indicator in line)
        return indicator_count >= 2
    
    def _analyze_subscription_content(self, content: bytes) -> Dict:
        """
        分析订阅内容，提取节点数量和流量信息
        
        Args:
            content: 响应内容
            
        Returns:
            Dict: 包含分析结果的字典
        """
        try:
            content_str = content.decode('utf-8', errors='ignore')
            logger.debug(f"原始内容长度: {len(content_str)}")
            logger.debug(f"原始内容预览: {content_str[:200]}...")
            
            # 检查是否为Clash YAML格式
            if self._is_clash_yaml_format(content_str):
                logger.info("检测到Clash YAML格式，使用专用解析器")
                return self._analyze_clash_yaml_content(content_str)
            
            # 尝试Base64解码
            decoded_content = self._try_base64_decode(content_str)
            if decoded_content:
                logger.debug(f"Base64解码成功，解码后长度: {len(decoded_content)}")
                logger.debug(f"解码后内容预览: {decoded_content[:200]}...")
                # 使用解码后的内容进行分析
                content_to_analyze = decoded_content
            else:
                logger.debug("Base64解码失败，使用原始内容")
                content_to_analyze = content_str
            
            # 统计节点数量
            node_count = 0
            node_types = {
                'vmess': 0,
                'vless': 0,
                'trojan': 0,
                'ss': 0,
                'ssr': 0,
                'hysteria': 0,
                'hysteria2': 0,
                'http': 0,
                'https': 0,
                'socks5': 0,
                'other': 0
            }
            
            # 统计各种协议节点
            for line in content_to_analyze.split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('vmess://'):
                    node_count += 1
                    node_types['vmess'] += 1
                elif line.startswith('vless://'):
                    node_count += 1
                    node_types['vless'] += 1
                elif line.startswith('trojan://'):
                    node_count += 1
                    node_types['trojan'] += 1
                elif line.startswith('ss://'):
                    node_count += 1
                    node_types['ss'] += 1
                elif line.startswith('ssr://'):
                    node_count += 1
                    node_types['ssr'] += 1
                elif line.startswith('hysteria2://'):
                    node_count += 1
                    node_types['hysteria2'] += 1
                elif line.startswith('hysteria://'):
                    node_count += 1
                    node_types['hysteria'] += 1
                elif line.startswith('http://'):
                    node_count += 1
                    node_types['http'] += 1
                elif line.startswith('https://'):
                    node_count += 1
                    node_types['https'] += 1
                elif line.startswith('socks5://'):
                    node_count += 1
                    node_types['socks5'] += 1
                elif 'server=' in line and 'port=' in line:
                    # 可能是配置文件格式
                    node_count += 1
                    node_types['other'] += 1
                elif self._is_valid_node_line(line):
                    # 其他有效的节点行
                    node_count += 1
                    node_types['other'] += 1
            
            logger.debug(f"检测到节点数量: {node_count}")
            logger.debug(f"节点类型分布: {node_types}")
            
            # 尝试提取流量信息
            traffic_info = self._extract_traffic_info(content_to_analyze)
            
            return {
                'total_nodes': node_count,
                'node_types': node_types,
                'traffic_info': traffic_info,
                'content_preview': content_to_analyze[:200] + '...' if len(content_to_analyze) > 200 else content_to_analyze,
                'is_base64_decoded': decoded_content is not None,
                'is_clash_format': False
            }
            
        except Exception as e:
            logger.warning(f"内容分析失败: {e}")
            return {
                'total_nodes': 0,
                'node_types': {},
                'traffic_info': {},
                'content_preview': '内容解析失败',
                'is_base64_decoded': False,
                'is_clash_format': False
            }
    
    def _extract_traffic_info(self, content: str) -> Dict:
        """
        从订阅内容中提取流量信息
        
        Args:
            content: 订阅内容字符串
            
        Returns:
            Dict: 流量信息字典
        """
        traffic_info = {
            'total_traffic': None,
            'used_traffic': None,
            'remaining_traffic': None,
            'traffic_unit': 'GB',
            'expire_date': None,
            'reset_date': None
        }
        
        try:
            # 先尝试URL解码，以处理编码后的中文
            import urllib.parse
            decoded_content = urllib.parse.unquote(content)
            
            content_lower = decoded_content.lower()
            logger.debug(f"开始提取流量信息，内容长度: {len(content)}")
            logger.debug(f"URL解码后内容预览: {decoded_content[:500]}...")
            
            # 查找流量相关信息
            import re
            
            # 匹配总流量 (如: 100GB, 500MB, 1TB)
            total_patterns = [
                r'总流量[：:]\s*(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)',
                r'total[:\s]*(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)',
                r'(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)\s*总流量',
                r'(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)\s*total',
                r'流量[：:]\s*(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)',
                r'bandwidth[:\s]*(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)',
                r'(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)',
                r'(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)\s*流量',
                # 添加更多Clash订阅中常见的流量格式
                r'upload[:\s]*(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)',
                r'download[:\s]*(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)',
                r'quota[:\s]*(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)'
            ]
            
            for pattern in total_patterns:
                match = re.search(pattern, content_lower)
                if match:
                    value = float(match.group(1))
                    unit = match.group(2).upper()
                    traffic_info['total_traffic'] = value
                    traffic_info['traffic_unit'] = unit
                    logger.debug(f"找到总流量: {value} {unit}")
                    break
            
            # 已用流量
            used_patterns = [
                r'已用流量[：:]\s*(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)',
                r'used[:\s]*(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)',
                r'(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)\s*已用',
                r'(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)\s*used',
                r'消耗[：:]\s*(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)',
                r'consumed[:\s]*(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)',
                # 添加更多格式
                r'uploaded[:\s]*(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)',
                r'downloaded[:\s]*(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)'
            ]
            
            for pattern in used_patterns:
                match = re.search(pattern, content_lower)
                if match:
                    value = float(match.group(1))
                    unit = match.group(2).upper()
                    traffic_info['used_traffic'] = value
                    logger.debug(f"找到已用流量: {value} {unit}")
                    break
            
            # 剩余流量 - 增强对URL编码中文的支持
            remaining_patterns = [
                r'剩余流量[：:]\s*(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)',
                r'remaining[:\s]*(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)',
                r'(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)\s*剩余',
                r'(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)\s*remaining',
                r'可用[：:]\s*(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)',
                r'available[:\s]*(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)',
                r'(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)\s*可用',
                r'(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)\s*available',
                # 添加更多格式
                r'left[:\s]*(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)',
                r'balance[:\s]*(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)',
                # 支持URL编码后的中文
                r'%E5%89%A9%E4%BD%99%E6%B5%81%E9%87%8F.*?(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)',
                # 支持直接从节点名称中提取流量信息
                r'#.*?(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)',
                r'#.*剩余.*?(\d+(?:\.\d+)?)\s*(gb|mb|tb|b)'
            ]
            
            for pattern in remaining_patterns:
                match = re.search(pattern, content_lower)
                if match:
                    value = float(match.group(1))
                    unit = match.group(2).upper()
                    traffic_info['remaining_traffic'] = value
                    logger.debug(f"找到剩余流量: {value} {unit}")
                    break
            
            # 智能计算缺失的流量信息
            self._calculate_missing_traffic_info(traffic_info)
            
            # 查找过期时间 - 支持更多格式
            expire_patterns = [
                r'过期时间[：:]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                r'expire[:\s]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                r'到期时间[：:]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})\s*过期',
                r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})\s*到期',
                r'有效期[：:]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                r'valid[:\s]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                # 添加更多格式
                r'expires[:\s]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                r'valid_until[:\s]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                r'end_date[:\s]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})'
            ]
            
            for pattern in expire_patterns:
                match = re.search(pattern, content_lower)
                if match:
                    traffic_info['expire_date'] = match.group(1)
                    logger.debug(f"找到过期时间: {match.group(1)}")
                    break
            
            # 查找重置时间
            reset_patterns = [
                r'重置时间[：:]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                r'reset[:\s]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})\s*重置',
                r'流量重置[：:]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                # 添加更多格式
                r'reset_date[:\s]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                r'next_reset[:\s]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})'
            ]
            
            for pattern in reset_patterns:
                match = re.search(pattern, content_lower)
                if match:
                    traffic_info['reset_date'] = match.group(1)
                    logger.debug(f"找到重置时间: {match.group(1)}")
                    break
            
            # 记录提取结果
            logger.debug(f"流量信息提取结果: {traffic_info}")
            
        except Exception as e:
            logger.warning(f"流量信息提取失败: {e}")
        
        return traffic_info
    
    def _calculate_missing_traffic_info(self, traffic_info: Dict):
        """
        智能计算缺失的流量信息，处理单位转换和计算逻辑
        
        Args:
            traffic_info: 流量信息字典
        """
        try:
            # 获取所有可用的流量信息
            total = traffic_info.get('total_traffic')
            used = traffic_info.get('used_traffic')
            remaining = traffic_info.get('remaining_traffic')
            unit = traffic_info.get('traffic_unit', 'GB')
            
            logger.debug(f"开始计算缺失流量信息: 总流量={total}, 已用={used}, 剩余={remaining}, 单位={unit}")
            
            # 如果三个值都有，验证一致性
            if total is not None and used is not None and remaining is not None:
                # 检查单位是否一致，如果不一致需要转换
                if self._validate_traffic_consistency(float(total), float(used), float(remaining), unit):
                    logger.debug("流量信息一致，无需计算")
                    return
                else:
                    logger.warning("流量信息不一致，尝试重新计算")
            
            # 计算缺失的流量信息
            if total is not None and used is not None and remaining is None:
                # 计算剩余流量
                if self._is_same_unit(total, used, unit):
                    traffic_info['remaining_traffic'] = total - used
                    logger.debug(f"计算得到剩余流量: {traffic_info['remaining_traffic']} {unit}")
                else:
                    # 单位不同，需要转换
                    converted_used = self._convert_to_unit(used, unit)
                    traffic_info['remaining_traffic'] = total - converted_used
                    logger.debug(f"单位转换后计算剩余流量: {traffic_info['remaining_traffic']} {unit}")
            
            elif total is not None and remaining is not None and used is None:
                # 计算已用流量
                if self._is_same_unit(total, remaining, unit):
                    traffic_info['used_traffic'] = total - remaining
                    logger.debug(f"计算得到已用流量: {traffic_info['used_traffic']} {unit}")
                else:
                    # 单位不同，需要转换
                    converted_remaining = self._convert_to_unit(remaining, unit)
                    traffic_info['used_traffic'] = total - converted_remaining
                    logger.debug(f"单位转换后计算已用流量: {traffic_info['used_traffic']} {unit}")
            
            elif used is not None and remaining is not None and total is None:
                # 计算总流量
                if self._is_same_unit(used, remaining, unit):
                    traffic_info['total_traffic'] = used + remaining
                    logger.debug(f"计算得到总流量: {traffic_info['total_traffic']} {unit}")
                else:
                    # 单位不同，需要转换
                    converted_remaining = self._convert_to_unit(remaining, unit)
                    traffic_info['total_traffic'] = used + converted_remaining
                    logger.debug(f"单位转换后计算总流量: {traffic_info['total_traffic']} {unit}")
            
            # 统一单位到标准单位（GB）
            self._normalize_traffic_units(traffic_info)
            
        except Exception as e:
            logger.warning(f"流量计算失败: {e}")
    
    def _validate_traffic_consistency(self, total: float, used: float, remaining: float, unit: str) -> bool:
        """
        验证流量信息的一致性
        
        Args:
            total: 总流量
            used: 已用流量
            remaining: 剩余流量
            unit: 单位
            
        Returns:
            bool: 是否一致
        """
        try:
            # 检查是否满足: total = used + remaining
            tolerance = 0.01  # 允许1%的误差
            expected_total = used + remaining
            difference = abs(total - expected_total)
            
            if difference <= tolerance * total:
                logger.debug(f"流量信息一致: {total} = {used} + {remaining}")
                return True
            else:
                logger.warning(f"流量信息不一致: {total} != {used} + {remaining}, 差值: {difference}")
                return False
                
        except Exception as e:
            logger.debug(f"流量一致性验证失败: {e}")
            return False
    
    def _is_same_unit(self, value1: float, value2: float, unit: str) -> bool:
        """
        检查两个值是否使用相同单位
        
        Args:
            value1: 第一个值
            value2: 第二个值
            unit: 单位
            
        Returns:
            bool: 是否相同单位
        """
        # 这里简化处理，假设如果都使用相同的单位字段，就是相同单位
        return True
    
    def _convert_to_unit(self, value: float, target_unit: str) -> float:
        """
        将流量值转换到目标单位
        
        Args:
            value: 原始值
            target_unit: 目标单位
            
        Returns:
            float: 转换后的值
        """
        # 这里可以根据需要实现单位转换逻辑
        # 暂时返回原值，避免复杂的单位转换
        return value
    
    def _normalize_traffic_units(self, traffic_info: Dict):
        """
        将流量单位统一到标准单位（GB）
        
        Args:
            traffic_info: 流量信息字典
        """
        try:
            unit = traffic_info.get('traffic_unit', 'GB')
            
            # 如果已经是GB，无需转换
            if unit == 'GB':
                return
            
            # 转换系数
            conversion_factors = {
                'B': 1 / (1024**3),      # B to GB
                'KB': 1 / (1024**2),     # KB to GB
                'MB': 1 / 1024,          # MB to GB
                'GB': 1,                 # GB to GB
                'TB': 1024               # TB to GB
            }
            
            factor = conversion_factors.get(unit.upper(), 1)
            
            # 转换流量值
            if traffic_info.get('total_traffic') is not None:
                traffic_info['total_traffic'] = round(traffic_info['total_traffic'] * factor, 2)
            
            if traffic_info.get('used_traffic') is not None:
                traffic_info['used_traffic'] = round(traffic_info['used_traffic'] * factor, 2)
            
            if traffic_info.get('remaining_traffic') is not None:
                traffic_info['remaining_traffic'] = round(traffic_info['remaining_traffic'] * factor, 2)
            
            # 更新单位
            traffic_info['traffic_unit'] = 'GB'
            logger.debug(f"流量单位已统一到GB")
            
        except Exception as e:
            logger.warning(f"流量单位统一失败: {e}")
    
    def _is_clash_yaml_format(self, content: str) -> bool:
        """
        判断内容是否为Clash YAML格式
        
        Args:
            content: 内容字符串
            
        Returns:
            bool: 是否为Clash YAML格式
        """
        try:
            content_lower = content.lower()
            
            # Clash YAML格式的特征
            clash_indicators = [
                'proxies:',
                'proxy-groups:',
                'rules:',
                'mixed-port:',
                'allow-lan:',
                'mode:',
                'log-level:',
                'external-controller:',
                'secret:',
                'external-ui:'
            ]
            
            # 检查是否包含多个Clash特征
            indicator_count = sum(1 for indicator in clash_indicators if indicator in content_lower)
            is_clash = indicator_count >= 2
            
            logger.debug(f"Clash YAML格式检测: 找到 {indicator_count} 个特征，判断为: {is_clash}")
            return is_clash
            
        except Exception as e:
            logger.debug(f"Clash YAML格式检测失败: {e}")
            return False
    
    def _analyze_clash_yaml_content(self, content: str) -> Dict:
        """
        分析Clash YAML格式内容，提取节点和流量信息
        
        Args:
            content: Clash YAML内容字符串
            
        Returns:
            Dict: 包含分析结果的字典
        """
        try:
            logger.info("开始解析Clash YAML格式内容")
            logger.debug(f"原始内容长度: {len(content)}")
            logger.debug(f"内容预览: {content[:500]}...")
            
            # 统计节点数量
            node_count = 0
            node_types = {
                'vmess': 0,
                'vless': 0,
                'trojan': 0,
                'ss': 0,
                'ssr': 0,
                'http': 0,
                'https': 0,
                'socks5': 0,
                'other': 0
            }
            
            # 使用更强大的YAML解析逻辑
            lines = content.split('\n')
            in_proxies_section = False
            current_proxy = {}
            indent_level = 0
            
            for i, line in enumerate(lines):
                original_line = line
                line = line.rstrip()
                
                # 跳过空行和注释
                if not line or line.startswith('#'):
                    continue
                
                # 计算缩进级别
                current_indent = len(line) - len(line.lstrip())
                
                # 检查是否进入proxies部分
                if line.strip() == 'proxies:':
                    in_proxies_section = True
                    indent_level = current_indent
                    logger.debug(f"进入proxies部分，缩进级别: {indent_level}")
                    continue
                
                # 如果不在proxies部分，跳过
                if not in_proxies_section:
                    continue
                
                # 检查是否离开proxies部分
                if current_indent <= indent_level and line.strip() != 'proxies:':
                    # 检查是否是其他顶级配置项
                    if ':' in line and not line.endswith(':'):
                        key = line.split(':')[0].strip()
                        if key in ['proxy-groups', 'rules', 'mixed-port', 'allow-lan', 'mode', 'log-level', 'dns', 'tun', 'experimental']:
                            in_proxies_section = False
                            logger.debug(f"离开proxies部分，遇到配置项: {key}")
                            continue
                
                # 解析代理配置
                if in_proxies_section and current_indent > indent_level:
                    # 检查是否是新的代理节点
                    if line.strip().startswith('- name:'):
                        # 统计前一个代理节点
                        if current_proxy:
                            self._count_proxy_node(current_proxy, node_types)
                            node_count += 1
                            logger.debug(f"解析代理节点: {current_proxy.get('name', 'unknown')}")
                        
                        # 开始新的代理节点
                        current_proxy = {'name': line.split(':', 1)[1].strip().strip('"\'')}
                    elif current_proxy and ':' in line:
                        # 解析代理属性
                        key_value = line.strip().split(':', 1)
                        if len(key_value) == 2:
                            key = key_value[0].strip()
                            value = key_value[1].strip().strip('"\'')
                            current_proxy[key] = value
            
            # 统计最后一个代理节点
            if current_proxy:
                self._count_proxy_node(current_proxy, node_types)
                node_count += 1
                logger.debug(f"解析最后一个代理节点: {current_proxy.get('name', 'unknown')}")
            
            logger.info(f"Clash YAML解析完成，检测到节点数量: {node_count}")
            logger.debug(f"节点类型分布: {node_types}")
            
            # 尝试提取流量信息
            traffic_info = self._extract_traffic_info(content)
            
            # 如果没有从内容中提取到流量信息，尝试从URL参数中提取
            if not traffic_info.get('total_traffic') and not traffic_info.get('remaining_traffic'):
                # 这里可以添加从URL参数中提取流量信息的逻辑
                pass
            
            return {
                'total_nodes': node_count,
                'node_types': node_types,
                'traffic_info': traffic_info,
                'content_preview': content[:200] + '...' if len(content) > 200 else content,
                'is_base64_decoded': False,
                'is_clash_format': True
            }
            
        except Exception as e:
            logger.warning(f"Clash YAML内容分析失败: {e}")
            import traceback
            logger.debug(f"错误详情: {traceback.format_exc()}")
            return {
                'total_nodes': 0,
                'node_types': {},
                'traffic_info': {},
                'content_preview': 'Clash YAML解析失败',
                'is_base64_decoded': False,
                'is_clash_format': True
            }
    
    def _count_proxy_node(self, proxy: Dict, node_types: Dict):
        """
        统计代理节点类型
        
        Args:
            proxy: 代理节点配置字典
            node_types: 节点类型统计字典
        """
        try:
            proxy_type = proxy.get('type', '').lower()
            
            if proxy_type == 'vmess':
                node_types['vmess'] += 1
            elif proxy_type == 'vless':
                node_types['vless'] += 1
            elif proxy_type == 'trojan':
                node_types['trojan'] += 1
            elif proxy_type == 'ss':
                node_types['ss'] += 1
            elif proxy_type == 'ssr':
                node_types['ssr'] += 1
            elif proxy_type == 'http':
                node_types['http'] += 1
            elif proxy_type == 'https':
                node_types['https'] += 1
            elif proxy_type == 'socks5':
                node_types['socks5'] += 1
            else:
                node_types['other'] += 1
                
        except Exception as e:
            logger.debug(f"统计代理节点类型失败: {e}")
            node_types['other'] += 1
    
    def _dual_analyze_subscription(self, original_url: str, original_content: bytes) -> Dict:
        """
        双重分析订阅内容：比较原始base64和clash格式，如果不一致则使用订阅转换
        
        Args:
            original_url: 原始订阅URL
            original_content: 原始响应内容
            
        Returns:
            Dict: 包含分析结果的字典
        """
        logger.info("开始双重分析订阅内容")
        
        # 步骤1：分析原始base64内容 - 重新请求原始URL
        logger.info("步骤1：分析原始base64内容")
        original_decoded_content = None
        base64_result = {}
        
        try:
            # 重新请求原始URL（不带clash标志）获取真正的原始内容
            logger.info(f"重新请求原始URL获取base64内容: {original_url}")
            response = self.session.get(
                original_url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
                verify=False
            )
            
            if response.status_code == 200:
                original_content_str = response.content.decode('utf-8', errors='ignore')
                logger.info(f"原始内容长度: {len(original_content_str)}")
                logger.info(f"原始内容预览: {original_content_str[:200]}...")
                
                original_decoded_content = self._try_base64_decode(original_content_str)
                if original_decoded_content:
                    logger.info(f"原始内容base64解码成功，长度: {len(original_decoded_content)}")
                    logger.info(f"解码后内容预览: {original_decoded_content[:500]}...")
                    # 直接分析解码后的内容
                    base64_result = self._analyze_decoded_content(original_decoded_content)
                else:
                    logger.info("原始内容不是base64格式或解码失败")
                    original_decoded_content = original_content_str
                    base64_result = self._analyze_subscription_content(response.content)
            else:
                logger.error(f"重新请求原始URL失败，状态码: {response.status_code}")
                base64_result = self._analyze_subscription_content(original_content)
                
        except Exception as e:
            logger.error(f"原始内容处理失败: {e}")
            original_decoded_content = ""
            base64_result = self._analyze_subscription_content(original_content)
        
        # 步骤2：获取clash格式内容
        logger.info("步骤2：获取clash格式内容")
        clash_result, clash_content = self._analyze_with_clash_flag_and_content(original_url)
        
        # 步骤3：比较两种内容是否一致
        content_identical = False
        if clash_content and original_decoded_content:
            # 简单比较内容长度和前100字符
            content_identical = (
                abs(len(clash_content) - len(original_decoded_content)) < 100 and
                clash_content[:100] == original_decoded_content[:100]
            )
            logger.info(f"内容比较结果: {'一致' if content_identical else '不一致'}")
            logger.info(f"原始内容长度: {len(original_decoded_content)}, Clash内容长度: {len(clash_content) if clash_content else 0}")
        
        # 步骤4：根据比较结果选择处理方式
        if not content_identical and clash_content:
            logger.info("内容不一致，使用订阅地址转换服务")
            converted_result = self._convert_subscription_with_service(original_url, original_decoded_content)
            if converted_result and converted_result.get('total_nodes', 0) > 0:
                logger.info(f"订阅转换成功，找到 {converted_result['total_nodes']} 个节点")
                converted_result['analysis_method'] = 'subscription_converter'
                return converted_result
        
        # 步骤5：选择最佳结果
        if clash_result and clash_result.get('total_nodes', 0) > 0:
            logger.info(f"使用Clash格式结果，找到 {clash_result['total_nodes']} 个节点")
            clash_result['analysis_method'] = 'clash_flag'
            return clash_result
        elif base64_result and base64_result.get('total_nodes', 0) > 0:
            logger.info(f"使用base64解码结果，找到 {base64_result['total_nodes']} 个节点")
            base64_result['analysis_method'] = 'base64_decode'
            return base64_result
        
        # 都没有找到节点，返回clash结果（可能包含流量信息）
        if clash_result:
            logger.info("未找到节点，返回clash格式结果（可能包含流量信息）")
            clash_result['analysis_method'] = 'clash_flag_fallback'
            return clash_result
        
        # 最后返回base64结果
        logger.warning("所有方法都失败，返回base64分析结果")
        base64_result['analysis_method'] = 'base64_fallback'
        return base64_result
    
    def _analyze_with_clash_flag_and_content(self, original_url: str) -> tuple:
        """
        使用&flag=clash参数获取YAML格式进行分析，同时返回内容
        
        Args:
            original_url: 原始订阅URL
            
        Returns:
            tuple: (分析结果, 内容字符串)
        """
        try:
            # 构建clash URL
            if '&flag=clash' not in original_url and '?flag=clash' not in original_url:
                separator = '&' if '?' in original_url else '?'
                clash_url = f"{original_url}{separator}flag=clash"
            else:
                clash_url = original_url
            
            logger.info(f"尝试获取Clash格式: {clash_url}")
            
            # 请求clash格式
            response = self.session.get(
                clash_url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
                verify=False
            )
            
            if response.status_code == 200:
                content_str = response.content.decode('utf-8', errors='ignore')
                logger.info(f"获取到Clash格式内容，长度: {len(content_str)}")
                
                # 分析YAML内容
                if self._is_clash_yaml_format(content_str):
                    analysis_result = self._analyze_clash_yaml_content(content_str)
                    return analysis_result, content_str
                else:
                    logger.warning("返回的内容不是有效的Clash YAML格式")
                    return {}, content_str
            else:
                logger.warning(f"获取Clash格式失败，状态码: {response.status_code}")
                return {}, None
                
        except Exception as e:
            logger.error(f"使用&flag=clash分析失败: {e}")
            return {}, None
    
    def _convert_subscription_with_service(self, original_url: str, original_content: str) -> Dict:
        """
        使用订阅转换服务转换订阅链接
        
        Args:
            original_url: 原始订阅URL
            original_content: 原始内容
            
        Returns:
            Dict: 转换后的分析结果
        """
        try:
            logger.info("尝试使用订阅转换服务")
            
            # 常用的订阅转换服务
            converter_services = [
                "https://sub.xeton.dev/sub",
                "https://api.dler.io/sub",
                "https://subweb.s3.fr-par.scw.cloud/sub"
            ]
            
            for service_url in converter_services:
                try:
                    # 构建转换请求
                    convert_url = f"{service_url}?target=clash&url={original_url}&insert=false&config=https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/config/ACL4SSR_Online.ini"
                    
                    logger.info(f"尝试转换服务: {service_url}")
                    
                    # 请求转换
                    response = self.session.get(
                        convert_url,
                        timeout=REQUEST_TIMEOUT * 2,  # 转换服务可能比较慢
                        allow_redirects=True,
                        verify=False
                    )
                    
                    if response.status_code == 200:
                        converted_content = response.content.decode('utf-8', errors='ignore')
                        logger.info(f"转换服务成功，内容长度: {len(converted_content)}")
                        
                        # 分析转换后的内容
                        if self._is_clash_yaml_format(converted_content):
                            result = self._analyze_clash_yaml_content(converted_content)
                            if result.get('total_nodes', 0) > 0:
                                logger.info(f"转换服务 {service_url} 成功，找到 {result['total_nodes']} 个节点")
                                return result
                        else:
                            logger.warning(f"转换服务 {service_url} 返回的内容不是有效的Clash格式")
                    else:
                        logger.warning(f"转换服务 {service_url} 请求失败，状态码: {response.status_code}")
                        
                except Exception as e:
                    logger.error(f"转换服务 {service_url} 失败: {e}")
                    continue
            
            logger.warning("所有转换服务都失败")
            return {}
            
        except Exception as e:
            logger.error(f"订阅转换失败: {e}")
            return {}
    
    def _analyze_decoded_content(self, content: str) -> Dict:
        """
        直接分析解码后的内容，专门用于节点链接格式
        
        Args:
            content: 解码后的内容字符串
            
        Returns:
            Dict: 包含分析结果的字典
        """
        try:
            logger.info(f"开始分析解码后内容，长度: {len(content)}")
            
            # 统计节点数量
            node_count = 0
            node_types = {
                'vmess': 0,
                'vless': 0,
                'trojan': 0,
                'ss': 0,
                'ssr': 0,
                'hysteria': 0,
                'hysteria2': 0,
                'http': 0,
                'https': 0,
                'socks5': 0,
                'other': 0
            }
            
            # 统计各种协议节点
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('vmess://'):
                    node_count += 1
                    node_types['vmess'] += 1
                elif line.startswith('vless://'):
                    node_count += 1
                    node_types['vless'] += 1
                elif line.startswith('trojan://'):
                    node_count += 1
                    node_types['trojan'] += 1
                elif line.startswith('ss://'):
                    node_count += 1
                    node_types['ss'] += 1
                elif line.startswith('ssr://'):
                    node_count += 1
                    node_types['ssr'] += 1
                elif line.startswith('hysteria2://'):
                    node_count += 1
                    node_types['hysteria2'] += 1
                    logger.debug(f"发现hysteria2节点: {line[:100]}...")
                elif line.startswith('hysteria://'):
                    node_count += 1
                    node_types['hysteria'] += 1
                    logger.debug(f"发现hysteria节点: {line[:100]}...")
                elif line.startswith('http://'):
                    node_count += 1
                    node_types['http'] += 1
                elif line.startswith('https://'):
                    node_count += 1
                    node_types['https'] += 1
                elif line.startswith('socks5://'):
                    node_count += 1
                    node_types['socks5'] += 1
                elif self._is_valid_node_line(line):
                    # 其他有效的节点行
                    node_count += 1
                    node_types['other'] += 1
            
            logger.info(f"解码内容检测到节点数量: {node_count}")
            logger.info(f"节点类型分布: {node_types}")
            
            # 尝试提取流量信息
            traffic_info = self._extract_traffic_info(content)
            
            return {
                'total_nodes': node_count,
                'node_types': node_types,
                'traffic_info': traffic_info,
                'content_preview': content[:200] + '...' if len(content) > 200 else content,
                'is_base64_decoded': True,
                'is_clash_format': False,
                'analysis_method': 'base64_decode'
            }
            
        except Exception as e:
            logger.error(f"解码内容分析失败: {e}")
            return {
                'total_nodes': 0,
                'node_types': {},
                'traffic_info': {},
                'content_preview': '解码内容分析失败',
                'is_base64_decoded': True,
                'is_clash_format': False,
                'analysis_method': 'base64_decode_error'
            }

    def send_dingtalk_notification(self, result: Dict) -> bool:
        """
        发送钉钉通知（精简版）
        
        Args:
            result: 检测结果字典
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 提取并清理订阅链接
            raw_url = result['url']
            
            # 使用URL提取器进行清理
            from url_extractor import URLExtractor
            extractor = URLExtractor()
            
            # 提取订阅链接
            urls = extractor.extract_subscription_urls(raw_url)
            if urls:
                # 选择最长的URL（通常包含更多参数）
                clean_url = max(urls, key=len)
            else:
                # 如果提取失败，使用简单的清理方法
                clean_url = raw_url
                # 先处理HTML实体编码
                import html
                clean_url = html.unescape(clean_url)
                # 移除HTML标签
                clean_url = re.sub(r'<[^>]+>', '', clean_url)
                # 移除多余文本
                clean_url = re.sub(r'^[^h]*?(https?://)', r'\1', clean_url)
                clean_url = re.sub(r'<br/?>.*$', '', clean_url)
                clean_url = re.sub(r'<div[^>]*>.*$', '', clean_url)
                clean_url = clean_url.strip()
            
            # 移除clash标志
            if '&flag=clash' in clean_url:
                clean_url = clean_url.replace('&flag=clash', '')
            if '?flag=clash' in clean_url:
                clean_url = clean_url.replace('?flag=clash', '')
            
            # 标准化URL用于重复检查
            normalized_url = self.normalize_url(clean_url)
            
            # 检查是否已发送过通知（使用标准化URL）
            if normalized_url in self.notified_urls:
                logger.info(f"订阅链接已发送过钉钉通知，跳过: {normalized_url}")
                return True
            
            # 只发送可用的订阅链接通知
            if not result['available']:
                logger.debug(f"订阅链接不可用，跳过钉钉通知: {clean_url}")
                return True
            
            # 构建流量信息
            traffic_text = "未知"
            total_traffic_text = "未知"
            if result.get('traffic_info'):
                traffic = result['traffic_info']
                if traffic.get('remaining_traffic'):
                    traffic_text = f"剩余 {traffic['remaining_traffic']} {traffic.get('traffic_unit', 'GB')}"
                if traffic.get('total_traffic'):
                    total_traffic_text = f"总量 {traffic['total_traffic']} {traffic.get('traffic_unit', 'GB')}"
                    if not traffic.get('remaining_traffic'):
                        traffic_text = total_traffic_text
            
            # 构建节点信息和协议信息
            node_count = 0
            protocols_text = "未知"
            if result.get('node_analysis'):
                analysis = result['node_analysis']
                node_count = analysis.get('total_nodes', 0)
                
                # 获取协议统计
                node_types = analysis.get('node_types', {})
                if node_types:
                    protocol_list = []
                    for protocol, count in node_types.items():
                        if count > 0:
                            protocol_list.append(f"{protocol}({count})")
                    protocols_text = ", ".join(protocol_list) if protocol_list else "未知"
            
            title = "✅ 发现可用订阅"
            
            # 获取分析方法信息
            analysis_method = "未知"
            if result.get('node_analysis'):
                method = result['node_analysis'].get('analysis_method', 'unknown')
                if method == 'clash_flag':
                    analysis_method = "Clash格式"
                elif method == 'base64_decode':
                    analysis_method = "Base64解码"
                elif method == 'subscription_converter':
                    analysis_method = "订阅转换"
                elif method in ['clash_flag_fallback', 'base64_fallback']:
                    analysis_method = f"备用方案({method.split('_')[0]})"
            
            # 分成三条消息发送：1. Link卡片  2. @all提醒  3. 分析结果
            
            # 第一条消息：Link卡片（支持复制功能）
            link_message = {
                "msgtype": "link",
                "link": {
                    "title": "✅ 发现可用订阅",
                    "text": f"节点: {node_count} 个 | 协议: {protocols_text} | 剩余: {traffic_text}",
                    "messageUrl": clean_url,
                    "picUrl": "https://img.alicdn.com/tfs/TB1NwmBEL9TBuNjy1zbXXXpepXa-2400-1218.png"
                }
            }
            
            # 第二条消息：@all提醒（包含URL）
            url_message = {
                "msgtype": "text",
                "text": {
                    "content": f":{clean_url}"
                },
                "at": {
                    "isAtAll": True  # @所有人，提醒确认收到
                }
            }
            
            # 第三条消息：分析结果（添加时间信息）
            from datetime import datetime
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            info_content = f"""{title}

📊 分析结果：
• 状态: ✅ 可用
• 节点: {node_count} 个
• 协议: {protocols_text}
• 剩余: {traffic_text}
• 总量: {total_traffic_text}
• 方式: {analysis_method}
• 响应: {result.get('status_code', 'N/A')}

⏰ 发现时间: {current_time}
🤖 自动检测系统"""
            
            info_message = {
                "msgtype": "text",
                "text": {
                    "content": info_content
                },
                "at": {
                    "isAtAll": False
                }
            }
            
            # 发送第一条消息（Link卡片）
            response1 = requests.post(
                DINGTALK_WEBHOOK,
                json=link_message,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            # 稍作延迟，确保消息顺序
            import time
            time.sleep(0.5)
            
            # 发送第二条消息（@all提醒）
            response2 = requests.post(
                DINGTALK_WEBHOOK,
                json=url_message,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            # 稍作延迟，确保消息顺序
            time.sleep(0.5)
            
            # 发送第三条消息（分析结果）
            response3 = requests.post(
                DINGTALK_WEBHOOK,
                json=info_message,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            # 检查三条消息的发送结果
            success1 = response1.status_code == 200 and response1.json().get('errcode') == 0
            success2 = response2.status_code == 200 and response2.json().get('errcode') == 0
            success3 = response3.status_code == 200 and response3.json().get('errcode') == 0
            
            if success1 and success2 and success3:
                logger.info("钉钉通知发送成功（Link卡片 + @all提醒 + 分析结果）")
                logger.info(f"Link卡片支持复制，@all提醒确认收到")
                
                # 使用专用的日志记录方法记录详细信息
                daily_logger.log_subscription_found(clean_url, result)
                daily_logger.log_dingtalk_sent(clean_url, True)
                
                # 记录已发送通知的URL并保存到文件（使用标准化URL）
                self.notified_urls.add(normalized_url)
                self._save_notified_urls()
                logger.info(f"已记录通知URL: {normalized_url}")
                
                return True
            else:
                if not success1:
                    logger.error(f"Link卡片消息发送失败: {response1.status_code} - {response1.json() if response1.status_code == 200 else 'HTTP错误'}")
                
                if not success2:
                    logger.error(f"@all提醒消息发送失败: {response2.status_code} - {response2.json() if response2.status_code == 200 else 'HTTP错误'}")
                
                if not success3:
                    logger.error(f"分析结果消息发送失败: {response3.status_code} - {response3.json() if response3.status_code == 200 else 'HTTP错误'}")
                
                return False
                
        except Exception as e:
            logger.error(f"发送钉钉通知失败: {e}")
            return False
    
    def send_serpapi_usage_notification(self, current_usage: int, total_quota: int, quotas_detail: List[Dict] = None) -> bool:
        """
        发送SerpAPI使用量阈值通知
        
        Args:
            current_usage: 当前已使用量
            total_quota: 总配额
            quotas_detail: 详细配额信息列表
            
        Returns:
            bool: 是否发送成功
        """
        try:
            from datetime import datetime
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 计算使用率
            usage_percentage = (current_usage / total_quota * 100) if total_quota > 0 else 0
            
            # 定义阈值列表 (10%, 20%, 30%, ...)
            thresholds = [10, 20, 30, 40, 50, 60, 70, 80, 90, 95]
            
            # 检查是否达到某个阈值
            reached_threshold = None
            for threshold in thresholds:
                if usage_percentage >= threshold:
                    reached_threshold = threshold
                else:
                    break
            
            # 只有达到阈值才发送通知
            if reached_threshold is None:
                logger.debug(f"SerpAPI使用率 {usage_percentage:.1f}% 未达到通知阈值")
                return True
            
            # 计算密钥统计信息
            total_keys = 0
            available_keys = 0
            failed_keys = 0
            key_details = []
            
            if quotas_detail and isinstance(quotas_detail, list):
                total_keys = len(quotas_detail)
                for i, quota_info in enumerate(quotas_detail, 1):
                    if quota_info and isinstance(quota_info, dict):
                        used = quota_info.get('this_month_usage', 0)
                        quota = quota_info.get('searches_per_month', 0)
                        
                        if quota > 0:
                            available_keys += 1
                            usage_rate = (used / quota * 100) if quota > 0 else 0
                            remaining = quota - used
                            
                            # 计算下次重置时间
                            next_reset_date = self._calculate_next_reset_date(quota_info, i)
                            
                            # 根据使用情况添加状态标识
                            if usage_rate >= 90:
                                status = "⚠️ 即将耗尽"
                            elif usage_rate >= 70:
                                status = "⚠️ 使用较多"
                            else:
                                status = "✅ 正常使用"
                            
                            key_details.append(f"• 密钥{i}: {used}/{quota} ({usage_rate:.1f}% 已用) - {status}")
                            key_details.append(f"  📅 下次重置: {next_reset_date}")
                        else:
                            failed_keys += 1
                            key_details.append(f"• 密钥{i}: ❌ 失效或无法访问")
            
            # 构建通知内容
            usage_content = f"""{current_time}
🎯 SerpAPI使用量提醒
使用率已达到 {reached_threshold}% 阈值

📈 汇总信息
• ✅ 可用密钥: {available_keys}/{total_keys} {'(全部可用)' if available_keys == total_keys else ''}
• ❌ 失效密钥: {failed_keys}/{total_keys} {'(无失效密钥)' if failed_keys == 0 else ''}

💰 额度汇总
• 🎯 总剩余搜索次数: {total_quota - current_usage}次
• 📅 总月度限制: {total_quota}次
• 📊 总已使用: {current_usage}次
• 📈 总体使用率: {usage_percentage:.1f}%"""

            if key_details:
                usage_content += "\n\n🔑 各密钥使用情况\n" + "\n".join(key_details)

            usage_content += f"""

⚠️ 使用量阈值提醒
• 当前使用率已达到 {reached_threshold}% 监控阈值
• 请注意API配额使用情况
• 建议合理安排搜索频率

🤖 自动监控系统"""

            # 构建钉钉消息
            usage_message = {
                "msgtype": "text",
                "text": {
                    "content": f":{usage_content}"
                },
                "at": {
                    "isAtAll": False
                }
            }

            # 发送钉钉通知
            import requests
            response = requests.post(
                self.dingtalk_webhook,
                json=usage_message,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    logger.info(f"✅ SerpAPI使用量阈值通知发送成功 (使用率: {usage_percentage:.1f}%, 阈值: {reached_threshold}%)")
                    return True
                else:
                    logger.error(f"❌ SerpAPI使用量阈值通知发送失败: {result}")
                    return False
            else:
                logger.error(f"❌ SerpAPI使用量阈值通知HTTP错误: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ SerpAPI使用量阈值通知发送异常: {e}")
            return False
    
    def check_multiple_subscriptions(self, urls: List[str]) -> List[Dict]:
        """
        批量检测多个订阅链接
        
        Args:
            urls: 订阅链接列表
            
        Returns:
            List[Dict]: 检测结果列表
        """
        # 去除重复URL
        unique_urls, duplicate_mapping = self.remove_duplicate_urls(urls)
        
        # 打印重复分析结果
        self.print_duplicate_analysis(urls, duplicate_mapping)
        
        if not unique_urls:
            logger.warning("去重后没有有效的订阅链接")
            return []
        
        results = []
        
        for i, url in enumerate(unique_urls, 1):
            logger.info(f"正在检测第 {i}/{len(unique_urls)} 个订阅链接 (去重后)")
            result = self.check_subscription_url(url.strip())
            results.append(result)
            
            # 如果可用，发送钉钉通知
            if result['available']:
                self.send_dingtalk_notification(result)
            
            # 避免请求过于频繁
            if i < len(unique_urls):
                time.sleep(1)
        
        return results
    
    def save_results(self, results: List[Dict], filename: Optional[str] = None):
        """
        保存检测结果到文件
        
        Args:
            results: 检测结果列表
            filename: 文件名（可选）
        """
        if filename is None:
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            filename = f'subscription_check_results_{timestamp}.json'
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"检测结果已保存到: {filename}")
        except Exception as e:
            logger.error(f"保存结果失败: {e}")


def main():
    """主函数"""
    print("=" * 60)
    print("订阅链接可用性检测工具")
    print("=" * 60)
    
    # 创建检测器
    checker = SubscriptionChecker()
    
    # 测试代理连接
    proxy_test_result = checker.test_proxy()
    checker.print_proxy_test_result(proxy_test_result)

    # 获取用户输入
    print("\n请输入订阅链接（每行一个，输入空行结束）:")
    urls = []
    
    while True:
        url = input().strip()
        if not url:
            break
        urls.append(url)
    
    if not urls:
        print("未输入任何订阅链接，程序退出。")
        return
    
    print(f"\n开始检测 {len(urls)} 个订阅链接...")
    
    # 执行检测（自动去重）
    results = checker.check_multiple_subscriptions(urls)
    
    if not results:
        print("没有有效的订阅链接需要检测。")
        return
    
    # 显示结果摘要
    print("\n" + "=" * 60)
    print("检测结果摘要")
    print("=" * 60)
    
    available_count = sum(1 for r in results if r['available'])
    total_count = len(results)
    
    print(f"检测的链接数: {total_count} (已自动去重)")
    print(f"可用链接: {available_count}")
    print(f"不可用链接: {total_count - available_count}")
    
    # 显示详细结果
    print("\n详细结果:")
    for i, result in enumerate(results, 1):
        status_icon = "✅" if result['available'] else "❌"
        print(f"{i}. {status_icon} {result['url']}")
        print(f"   状态: {result['status']}")
        if result['error']:
            print(f"   错误: {result['error']}")
        if result['available']:
            print(f"   响应时间: {result['response_time']}秒")
            
            # 显示节点信息
            if result.get('node_analysis'):
                analysis = result['node_analysis']
                print(f"   节点数量: {analysis.get('total_nodes', 0)} 个")
                
                # 显示节点类型分布
                node_types = analysis.get('node_types', {})
                active_types = [f"{k.upper()}:{v}" for k, v in node_types.items() if v > 0]
                if active_types:
                    print(f"   节点类型: {', '.join(active_types)}")
                
                # 显示格式信息
                if analysis.get('is_clash_format'):
                    print(f"   格式: Clash YAML")
                elif analysis.get('is_base64_decoded'):
                    print(f"   格式: Base64编码")
                else:
                    print(f"   格式: 原始格式")
            
            # 显示流量信息
            if result.get('traffic_info'):
                traffic = result['traffic_info']
                traffic_details = []
                
                if traffic.get('total_traffic'):
                    traffic_details.append(f"总流量: {traffic['total_traffic']} {traffic['traffic_unit']}")
                if traffic.get('remaining_traffic'):
                    traffic_details.append(f"剩余流量: {traffic['remaining_traffic']} {traffic['traffic_unit']}")
                if traffic.get('expire_date'):
                    traffic_details.append(f"过期时间: {traffic['expire_date']}")
                
                if traffic_details:
                    print(f"   流量信息: {' | '.join(traffic_details)}")
        
        print()
    
    # 保存结果
    checker.save_results(results)
    
    print("检测完成！结果已保存到JSON文件中。")


if __name__ == "__main__":
    main()
