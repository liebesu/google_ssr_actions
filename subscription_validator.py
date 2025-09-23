#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订阅验证器 - 从subscription_checker.py中拆分出来的验证逻辑
专注于订阅链接的验证和内容分析
"""

import requests
import time
import re
import base64
from typing import Dict, Optional, List
from urllib.parse import urlparse
import logging
from config import config


class SubscriptionValidator:
    """订阅验证器"""
    
    def __init__(self, use_proxy: bool = None):
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        
        # 设置请求头
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        
        # 设置代理
        if use_proxy is None:
            use_proxy = config.is_proxy_enabled()
        
        if use_proxy:
            proxy_config = config.get_proxy_config()
            if proxy_config and self._test_proxy_connection(proxy_config):
                self.session.proxies.update(proxy_config)
                self.logger.info(f"已启用代理: {proxy_config}")
            else:
                self.logger.warning("代理连接失败，切换到直连模式")
        else:
            self.logger.info("未使用代理")
    
    def _test_proxy_connection(self, proxy_config: Dict[str, str]) -> bool:
        """测试代理连接"""
        try:
            test_session = requests.Session()
            test_session.proxies.update(proxy_config)
            test_session.headers.update({'User-Agent': self.session.headers['User-Agent']})
            
            response = test_session.get('http://httpbin.org/ip', timeout=5)
            if response.status_code == 200:
                self.logger.info(f"代理测试成功: {response.json().get('origin', 'Unknown IP')}")
                return True
            else:
                self.logger.warning(f"代理测试失败，状态码: {response.status_code}")
                return False
        except Exception as e:
            self.logger.warning(f"代理测试异常: {e}")
            return False
    
    def validate_url_format(self, url: str) -> tuple[bool, str, str]:
        """验证URL格式"""
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
        
        if not cleaned_url:
            return False, "", "URL为空或只包含特殊符号"
        
        # 自动添加Clash格式标识
        if 'api/v1/client/subscribe' in cleaned_url and '&flag=clash' not in cleaned_url:
            if '?' in cleaned_url:
                cleaned_url += '&flag=clash'
            else:
                cleaned_url += '?flag=clash'
        
        # 验证URL格式
        try:
            parsed_url = urlparse(cleaned_url)
            
            if not parsed_url.scheme:
                if not cleaned_url.startswith('//'):
                    cleaned_url = 'https://' + cleaned_url
                else:
                    cleaned_url = 'https:' + cleaned_url
                parsed_url = urlparse(cleaned_url)
            
            if not parsed_url.netloc:
                return False, cleaned_url, "无效的URL格式：缺少域名"
            
            if parsed_url.scheme not in ['http', 'https']:
                return False, cleaned_url, f"不支持的协议：{parsed_url.scheme}"
            
            return True, cleaned_url, ""
        except Exception as e:
            return False, cleaned_url, f"URL解析失败: {e}"
    
    def check_subscription_availability(self, url: str) -> Dict:
        """检查订阅链接可用性"""
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
            'traffic_info': {}
        }
        
        try:
            # 验证URL格式
            is_valid, cleaned_url, error_msg = self.validate_url_format(url)
            if not is_valid:
                result['error'] = error_msg
                result['status'] = 'invalid_url'
                return result
            
            result['cleaned_url'] = cleaned_url
            
            # 发送请求
            start_time = time.time()
            timeout = config.get('validation.request_timeout', 10)
            
            response = self.session.get(
                cleaned_url,
                timeout=timeout,
                allow_redirects=True,
                verify=False
            )
            
            response_time = time.time() - start_time
            result['response_time'] = round(response_time, 2)
            result['status_code'] = response.status_code
            result['content_length'] = len(response.content)
            
            if response.status_code == 200:
                # 检查内容是否有效
                if self._is_valid_subscription_content(response.content):
                    result['status'] = 'available'
                    result['available'] = True
                    
                    # 分析订阅内容
                    analysis_result = self._analyze_subscription_content(response.content)
                    result['node_analysis'] = analysis_result
                    result['traffic_info'] = analysis_result.get('traffic_info', {})
                    
                    self.logger.info(f"订阅链接可用: {url}, 节点数: {analysis_result.get('total_nodes', 0)}")
                else:
                    result['status'] = 'invalid_content'
                    result['error'] = "响应内容无效"
            else:
                result['status'] = 'http_error'
                result['error'] = f"HTTP状态码: {response.status_code}"
                
        except requests.exceptions.Timeout:
            result['status'] = 'timeout'
            result['error'] = "请求超时"
        except requests.exceptions.ConnectionError:
            result['status'] = 'connection_error'
            result['error'] = "连接错误"
        except Exception as e:
            result['status'] = 'unknown_error'
            result['error'] = str(e)
        
        return result
    
    def _is_valid_subscription_content(self, content: bytes) -> bool:
        """判断订阅内容是否有效"""
        try:
            content_str = content.decode('utf-8', errors='ignore')
            
            if len(content_str.strip()) < 10:
                return False
            
            # 检查是否包含常见的订阅格式标识
            valid_indicators = [
                'vmess://', 'vless://', 'trojan://', 'ss://', 'ssr://',
                'hysteria2://', 'http://', 'https://', 'socks5://',
                'server=', 'port=', 'password=', 'proxies:'
            ]
            
            has_valid_format = any(indicator in content_str.lower() for indicator in valid_indicators)
            
            # 检查是否包含明显的错误信息
            error_indicators = [
                'error', 'not found', '404', '403', '500', '502', '503',
                'access denied', 'forbidden', 'unauthorized'
            ]
            has_error = any(error in content_str.lower() for error in error_indicators)
            
            return has_valid_format and not has_error
            
        except Exception:
            return False
    
    def _analyze_subscription_content(self, content: bytes) -> Dict:
        """分析订阅内容"""
        try:
            content_str = content.decode('utf-8', errors='ignore')
            
            # 检查是否为Clash YAML格式
            if self._is_clash_yaml_format(content_str):
                return self._analyze_clash_yaml_content(content_str)
            
            # 尝试Base64解码
            decoded_content = self._try_base64_decode(content_str)
            if decoded_content:
                content_to_analyze = decoded_content
            else:
                content_to_analyze = content_str
            
            # 统计节点数量
            node_count = 0
            node_types = {
                'vmess': 0, 'vless': 0, 'trojan': 0, 'ss': 0, 'ssr': 0,
                'hysteria': 0, 'hysteria2': 0, 'http': 0, 'https': 0, 'socks5': 0, 'other': 0
            }
            
            for line in content_to_analyze.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                for protocol in ['vmess', 'vless', 'trojan', 'ss', 'ssr', 'hysteria2', 'hysteria', 'http', 'https', 'socks5']:
                    if line.startswith(f'{protocol}://'):
                        node_count += 1
                        node_types[protocol] += 1
                        break
                else:
                    if self._is_valid_node_line(line):
                        node_count += 1
                        node_types['other'] += 1
            
            # 提取流量信息
            traffic_info = self._extract_traffic_info(content_to_analyze)
            
            return {
                'total_nodes': node_count,
                'node_types': node_types,
                'traffic_info': traffic_info,
                'is_base64_decoded': decoded_content is not None,
                'is_clash_format': self._is_clash_yaml_format(content_str)
            }
            
        except Exception as e:
            self.logger.warning(f"内容分析失败: {e}")
            return {
                'total_nodes': 0,
                'node_types': {},
                'traffic_info': {},
                'is_base64_decoded': False,
                'is_clash_format': False
            }
    
    def _try_base64_decode(self, content: str) -> Optional[str]:
        """尝试Base64解码"""
        try:
            import base64
            cleaned_content = content.replace('\n', '').replace('\r', '').replace(' ', '').replace('\t', '').strip()
            
            if not self._looks_like_base64(cleaned_content):
                return None
            
            decoded_bytes = base64.b64decode(cleaned_content)
            decoded_str = decoded_bytes.decode('utf-8', errors='ignore')
            return decoded_str
        except Exception:
            return None
    
    def _looks_like_base64(self, content: str) -> bool:
        """判断内容是否像Base64编码"""
        if not content or len(content) < 20:
            return False
        
        valid_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')
        content_chars = set(content)
        invalid_chars = content_chars - valid_chars
        
        if len(invalid_chars) > 0 and len(invalid_chars) / len(content_chars) > 0.1:
            return False
        
        alphanumeric_count = sum(1 for c in content if c.isalnum())
        return alphanumeric_count / len(content) >= 0.6
    
    def _is_clash_yaml_format(self, content: str) -> bool:
        """判断是否为Clash YAML格式"""
        content_lower = content.lower()
        clash_indicators = [
            'proxies:', 'proxy-groups:', 'rules:', 'mixed-port:', 'allow-lan:',
            'mode:', 'log-level:', 'external-controller:'
        ]
        indicator_count = sum(1 for indicator in clash_indicators if indicator in content_lower)
        return indicator_count >= 2
    
    def _analyze_clash_yaml_content(self, content: str) -> Dict:
        """分析Clash YAML格式内容"""
        try:
            node_count = 0
            node_types = {
                'vmess': 0, 'vless': 0, 'trojan': 0, 'ss': 0, 'ssr': 0,
                'http': 0, 'https': 0, 'socks5': 0, 'other': 0
            }
            
            lines = content.split('\n')
            in_proxies_section = False
            current_proxy = {}
            
            for line in lines:
                line = line.rstrip()
                if not line or line.startswith('#'):
                    continue
                
                if line.strip() == 'proxies:':
                    in_proxies_section = True
                    continue
                
                if in_proxies_section:
                    if line.strip().startswith('- name:'):
                        if current_proxy:
                            self._count_proxy_node(current_proxy, node_types)
                            node_count += 1
                        current_proxy = {'name': line.split(':', 1)[1].strip().strip('"\'')}
                    elif current_proxy and ':' in line:
                        key_value = line.strip().split(':', 1)
                        if len(key_value) == 2:
                            key = key_value[0].strip()
                            value = key_value[1].strip().strip('"\'')
                            current_proxy[key] = value
            
            if current_proxy:
                self._count_proxy_node(current_proxy, node_types)
                node_count += 1
            
            traffic_info = self._extract_traffic_info(content)
            
            return {
                'total_nodes': node_count,
                'node_types': node_types,
                'traffic_info': traffic_info,
                'is_base64_decoded': False,
                'is_clash_format': True
            }
        except Exception as e:
            self.logger.warning(f"Clash YAML内容分析失败: {e}")
            return {
                'total_nodes': 0,
                'node_types': {},
                'traffic_info': {},
                'is_base64_decoded': False,
                'is_clash_format': True
            }
    
    def _count_proxy_node(self, proxy: Dict, node_types: Dict):
        """统计代理节点类型"""
        try:
            proxy_type = proxy.get('type', '').lower()
            if proxy_type in node_types:
                node_types[proxy_type] += 1
            else:
                node_types['other'] += 1
        except Exception:
            node_types['other'] += 1
    
    def _is_valid_node_line(self, line: str) -> bool:
        """判断一行是否包含有效的节点信息"""
        if not line or line.startswith('#'):
            return False
        
        node_indicators = [
            'server=', 'port=', 'password=', 'method=', 'protocol=',
            'obfs=', 'obfs_param=', 'remarks=', 'group=',
            'name=', 'type=', 'uuid=', 'path=', 'host='
        ]
        
        indicator_count = sum(1 for indicator in node_indicators if indicator in line)
        return indicator_count >= 2
    
    def _extract_traffic_info(self, content: str) -> Dict:
        """从订阅内容中提取流量信息"""
        traffic_info = {
            'total_traffic': None,
            'used_traffic': None,
            'remaining_traffic': None,
            'traffic_unit': 'GB',
            'expire_date': None
        }
        
        try:
            import urllib.parse
            decoded_content = urllib.parse.unquote(content)
            content_lower = decoded_content.lower()
            
            # 流量匹配模式
            patterns = [
                (r'总(?:流量|量)[:：]\s*([0-9.]+)\s*(tb|gb|mb)?', 'total'),
                (r'剩余(?:流量)?[:：]\s*([0-9.]+)\s*(tb|gb|mb)?', 'remaining'),
                (r'已用[:：]\s*([0-9.]+)\s*(tb|gb|mb)?', 'used'),
                (r'total\s*:?\s*([0-9.]+)\s*(tb|gb|mb)?', 'total'),
                (r'remaining\s*:?\s*([0-9.]+)\s*(tb|gb|mb)?', 'remaining'),
                (r'used\s*:?\s*([0-9.]+)\s*(tb|gb|mb)?', 'used'),
            ]
            
            for pattern, key in patterns:
                match = re.search(pattern, content_lower, flags=re.IGNORECASE)
                if match:
                    value = float(match.group(1))
                    unit = match.group(2) or 'GB'
                    traffic_info[f'{key}_traffic'] = value
                    traffic_info['traffic_unit'] = unit.upper()
            
            # 过期时间
            expire_patterns = [
                r'过期时间[：:]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                r'expire[:\s]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                r'到期时间[：:]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})'
            ]
            
            for pattern in expire_patterns:
                match = re.search(pattern, content_lower)
                if match:
                    traffic_info['expire_date'] = match.group(1)
                    break
        except Exception:
            pass
        
        return traffic_info
