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

def main():
    """主程序入口"""
    print("🚀 Google SSR 订阅链接搜索器")
    print("=" * 50)
    print(f"⏰ 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    try:
        # 初始化搜索器
        scraper = EnhancedGoogleAPIScraper()
        
        # 显示配置信息
        print(f"🔍 搜索查询: {scraper.search_query}")
        print(f"🌍 支持地区数量: {len(scraper.regions)} 个地区 (全球多语言覆盖)")
        
        # 显示批量地区搜索配置
        regions_config = scraper.config.get('regions', {})
        batch_count = regions_config.get('batch_count', 4)
        inter_region_delay = regions_config.get('inter_region_delay', 15)
        priority_regions = regions_config.get('priority_regions', [])
        use_priority_only = regions_config.get('use_priority_only', False)
        
        print(f"📍 搜索模式: {'批量地区搜索' if batch_count > 1 else '单地区搜索'}")
        if batch_count > 1:
            print(f"   每次搜索地区数: {batch_count}")
            print(f"   地区间延迟: {inter_region_delay} 秒")
            if use_priority_only and priority_regions:
                print(f"   优先地区: {', '.join(priority_regions)} (仅搜索优先地区)")
            elif priority_regions:
                print(f"   优先地区: {', '.join(priority_regions)} (优先但不限制)")
        
        print(f"⏱️  搜索时间范围: {scraper.config['search']['time_range']}")
        print(f"📊 每页最大结果数: {scraper.config['search']['max_results_per_query']}")
        print(f"📄 最大处理页面数: {scraper.config['search']['max_pages_to_process']}")
        print(f"🔄 定时任务间隔: {scraper.config['schedule']['interval_hours']} 小时")
        print(f"🔔 钉钉通知: {'启用' if scraper.config['validation']['send_notifications'] else '禁用'}")
        print(f"🌐 代理设置: {'启用' if scraper.config['proxy']['enabled'] else '禁用'}")
        if scraper.config['proxy']['enabled']:
            proxy_url = f"{scraper.config['proxy']['protocol']}://{scraper.config['proxy']['host']}:{scraper.config['proxy']['port']}"
            print(f"   代理地址: {proxy_url}")
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
