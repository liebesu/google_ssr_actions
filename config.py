#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
统一管理项目配置，避免硬编码
"""

import os
import json
from typing import Dict, Any, Optional

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: str = 'scraper_config.json'):
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        default_config = {
            "proxy": {
                "enabled": os.getenv('PROXY_ENABLED', 'false').lower() == 'true',
                "host": os.getenv('PROXY_HOST', '192.168.100.110'),
                "port": int(os.getenv('PROXY_PORT', '7893')),
                "protocol": os.getenv('PROXY_PROTOCOL', 'http')
            },
            "dingtalk": {
                "webhook": os.getenv('DINGTALK_WEBHOOK', 'https://oapi.dingtalk.com/robot/send?access_token=' + os.getenv('DINGTALK_TOKEN', '')),
                "keyword": os.getenv('DINGTALK_KEYWORD', ':')
            },
            "search": {
                "time_range": os.getenv('SEARCH_TIME_RANGE', 'past_24_hours'),
                "max_results_per_query": int(os.getenv('MAX_RESULTS_PER_QUERY', '100')),
                "max_pages_to_process": int(os.getenv('MAX_PAGES_TO_PROCESS', '30')),
                "use_serpapi": os.getenv('USE_SERPAPI', 'true').lower() == 'true'
            },
            "validation": {
                "enabled": os.getenv('VALIDATION_ENABLED', 'true').lower() == 'true',
                "save_only_available": os.getenv('SAVE_ONLY_AVAILABLE', 'true').lower() == 'true',
                "send_notifications": os.getenv('SEND_NOTIFICATIONS', 'true').lower() == 'true',
                "request_timeout": int(os.getenv('REQUEST_TIMEOUT', '10'))
            },
            "schedule": {
                "interval_hours": int(os.getenv('SCHEDULE_INTERVAL_HOURS', '2')),
                "immediate_run": os.getenv('IMMEDIATE_RUN', 'true').lower() == 'true'
            },
            "rate_limiting": {
                "serpapi_request_delay": int(os.getenv('SERPAPI_REQUEST_DELAY', '10')),
                "min_interval_minutes": int(os.getenv('MIN_INTERVAL_MINUTES', '30')),
                "max_requests_per_hour": int(os.getenv('MAX_REQUESTS_PER_HOUR', '6'))
            },
            "regions": {
                "batch_count": int(os.getenv('REGION_BATCH_COUNT', '4')),
                "inter_region_delay": int(os.getenv('INTER_REGION_DELAY', '15')),
                "priority_regions": os.getenv('PRIORITY_REGIONS', 'cn,hk,tw,us,sg,jp,kr,de').split(','),
                "use_priority_only": os.getenv('USE_PRIORITY_ONLY', 'false').lower() == 'true'
            }
        }
        
        # 如果配置文件存在，加载并合并
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    default_config.update(file_config)
            except Exception as e:
                print(f"配置文件加载失败，使用默认配置: {e}")
        
        return default_config
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_dingtalk_webhook(self) -> Optional[str]:
        """获取钉钉Webhook URL"""
        webhook = self.get('dingtalk.webhook')
        if not webhook or 'your_token_here' in webhook:
            return None
        return webhook
    
    def is_proxy_enabled(self) -> bool:
        """检查代理是否启用"""
        # 在CI环境中禁用代理
        if os.getenv('GITHUB_ACTIONS') == 'true' or os.getenv('DISABLE_PROXY') == '1':
            return False
        return self.get('proxy.enabled', False)
    
    def get_proxy_config(self) -> Optional[Dict[str, str]]:
        """获取代理配置"""
        if not self.is_proxy_enabled():
            return None
        
        host = self.get('proxy.host')
        port = self.get('proxy.port')
        protocol = self.get('proxy.protocol', 'http')
        
        if not host or not port:
            return None
        
        proxy_url = f"{protocol}://{host}:{port}"
        return {
            'http': proxy_url,
            'https': proxy_url
        }
    
    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置文件失败: {e}")

# 全局配置实例
config = ConfigManager()

