#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google SSR 订阅链接搜索器 - 主程序入口
集成智能密钥管理、钉钉通知、URL提取和去重功能
"""

import sys
import os
import json
import time
import logging
from datetime import datetime

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from google_api_scraper_enhanced import EnhancedGoogleAPIScraper
from logger_config import get_scraper_logger
from config import config
from error_handler import ErrorHandler, safe_execute

def main():
    """主程序入口"""
    print("🚀 Google SSR 订阅链接搜索器")
    print("=" * 50)
    print(f"⏰ 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    try:
        # 初始化错误处理器
        error_handler = ErrorHandler()
        
        # 安全初始化搜索器
        scraper = safe_execute(
            EnhancedGoogleAPIScraper,
            default_return=None,
            logger=logging.getLogger(__name__)
        )
        
        if scraper is None:
            print("❌ 搜索器初始化失败")
            sys.exit(1)
        
        # 显示配置信息
        print(f"🔍 搜索查询: {scraper.search_query}")
        print(f"🌍 支持地区数量: {len(scraper.regions)} 个地区 (全球多语言覆盖)")
        
        # 使用统一配置管理器获取配置信息
        batch_count = config.get('regions.batch_count', 4)
        inter_region_delay = config.get('regions.inter_region_delay', 15)
        priority_regions = config.get('regions.priority_regions', [])
        use_priority_only = config.get('regions.use_priority_only', False)
        
        print(f"📍 搜索模式: {'批量地区搜索' if batch_count > 1 else '单地区搜索'}")
        if batch_count > 1:
            print(f"   每次搜索地区数: {batch_count}")
            print(f"   地区间延迟: {inter_region_delay} 秒")
            if use_priority_only and priority_regions:
                print(f"   优先地区: {', '.join(priority_regions)} (仅搜索优先地区)")
            elif priority_regions:
                print(f"   优先地区: {', '.join(priority_regions)} (优先但不限制)")
        
        print(f"⏱️  搜索时间范围: {config.get('search.time_range', 'past_24_hours')}")
        print(f"📊 每页最大结果数: {config.get('search.max_results_per_query', 100)}")
        print(f"📄 最大处理页面数: {config.get('search.max_pages_to_process', 30)}")
        print(f"🔄 定时任务间隔: {config.get('schedule.interval_hours', 2)} 小时")
        print(f"🔔 钉钉通知: {'启用' if config.get('validation.send_notifications', True) else '禁用'}")
        print(f"🌐 代理设置: {'启用' if config.is_proxy_enabled() else '禁用'}")
        
        proxy_config = config.get_proxy_config()
        if proxy_config:
            print(f"   代理地址: {proxy_config.get('http', 'N/A')}")
        print("=" * 50)
        
        # 启动定时任务调度器
        scraper.start_scheduler()
        
    except KeyboardInterrupt:
        print("\n🛑 收到中断信号，正在停止...")
        sys.exit(0)
    except Exception as e:
        print(f"❌ 程序启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
