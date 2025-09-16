#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订阅URL历史检查器
用于检查订阅URL是否在历史记录中存在过
"""

import json
import re
import os
from typing import Set, List, Dict, Optional


class URLHistoryChecker:
    """订阅URL历史检查器"""
    
    def __init__(self, discovered_urls_file: str = 'discovered_urls.json', 
                 notified_urls_file: str = 'notified_urls.txt'):
        """
        初始化历史检查器
        
        Args:
            discovered_urls_file: 已发现URL文件路径
            notified_urls_file: 已通知URL文件路径
        """
        self.discovered_urls_file = discovered_urls_file
        self.notified_urls_file = notified_urls_file
        self.discovered_urls = self.load_discovered_urls()
        self.notified_urls = self.load_notified_urls()
        
        # 为了提高查询效率，预处理基础URL映射
        self.base_url_mapping = self._build_base_url_mapping()
        
    def load_discovered_urls(self) -> Set[str]:
        """加载已发现的订阅链接"""
        try:
            if os.path.exists(self.discovered_urls_file):
                with open(self.discovered_urls_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 过滤掉非字符串项（如时间戳）
                    return set([url for url in data if isinstance(url, str) and url.startswith('http')])
            return set()
        except Exception as e:
            print(f"❌ 加载已发现URL失败: {e}")
            return set()
    
    def load_notified_urls(self) -> Set[str]:
        """加载已通知的订阅链接"""
        try:
            if os.path.exists(self.notified_urls_file):
                with open(self.notified_urls_file, 'r', encoding='utf-8') as f:
                    return set([line.strip() for line in f if line.strip() and line.strip().startswith('http')])
            return set()
        except Exception as e:
            print(f"❌ 加载已通知URL失败: {e}")
            return set()
    
    def extract_base_subscription_url(self, url: str) -> str:
        """
        提取订阅URL的基础部分，用于去重比较
        移除流量信息、额外参数等，只保留核心的订阅地址
        """
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
    
    def _build_base_url_mapping(self) -> Dict[str, str]:
        """构建基础URL到原始URL的映射，用于快速查询"""
        mapping = {}
        
        # 处理已发现的URL
        for url in self.discovered_urls:
            base_url = self.extract_base_subscription_url(url)
            if base_url not in mapping:
                mapping[base_url] = url
        
        # 处理已通知的URL  
        for url in self.notified_urls:
            base_url = self.extract_base_subscription_url(url)
            if base_url not in mapping:
                mapping[base_url] = url
                
        return mapping
    
    def check_url_exists(self, url: str) -> Dict[str, any]:
        """
        检查URL是否在历史中存在
        
        Args:
            url: 要检查的订阅URL
            
        Returns:
            dict: 检查结果
                - exists: 是否存在
                - in_discovered: 是否在已发现列表中
                - in_notified: 是否在已通知列表中
                - base_url: 基础URL
                - matched_url: 匹配到的历史URL（如果存在）
        """
        base_url = self.extract_base_subscription_url(url)
        
        # 检查是否在基础URL映射中
        exists_in_base = base_url in self.base_url_mapping
        matched_url = self.base_url_mapping.get(base_url)
        
        # 详细检查在哪个列表中
        in_discovered = any(
            self.extract_base_subscription_url(discovered_url) == base_url 
            for discovered_url in self.discovered_urls
        )
        
        in_notified = any(
            self.extract_base_subscription_url(notified_url) == base_url 
            for notified_url in self.notified_urls
        )
        
        return {
            'exists': exists_in_base or in_discovered or in_notified,
            'in_discovered': in_discovered,
            'in_notified': in_notified,
            'base_url': base_url,
            'matched_url': matched_url,
            'original_url': url
        }
    
    def check_multiple_urls(self, urls: List[str]) -> List[Dict[str, any]]:
        """
        批量检查多个URL
        
        Args:
            urls: URL列表
            
        Returns:
            List[dict]: 检查结果列表
        """
        return [self.check_url_exists(url) for url in urls]
    
    def get_statistics(self) -> Dict[str, int]:
        """获取历史记录统计信息"""
        return {
            'discovered_count': len(self.discovered_urls),
            'notified_count': len(self.notified_urls),
            'unique_base_urls': len(self.base_url_mapping),
            'total_unique_urls': len(self.discovered_urls | self.notified_urls)
        }
    
    def find_similar_urls(self, url: str) -> List[str]:
        """
        查找相似的URL（相同基础URL但参数不同）
        
        Args:
            url: 查询URL
            
        Returns:
            List[str]: 相似URL列表
        """
        base_url = self.extract_base_subscription_url(url)
        similar_urls = []
        
        # 在已发现URL中查找
        for discovered_url in self.discovered_urls:
            if self.extract_base_subscription_url(discovered_url) == base_url:
                similar_urls.append(discovered_url)
        
        # 在已通知URL中查找
        for notified_url in self.notified_urls:
            if self.extract_base_subscription_url(notified_url) == base_url:
                similar_urls.append(notified_url)
        
        return list(set(similar_urls))


def main():
    """主函数 - 交互式命令行工具"""
    print("🔍 订阅URL历史检查器")
    print("=" * 50)
    
    # 初始化检查器
    try:
        checker = URLHistoryChecker()
        stats = checker.get_statistics()
        print(f"📊 历史记录统计:")
        print(f"   已发现URL数量: {stats['discovered_count']}")
        print(f"   已通知URL数量: {stats['notified_count']}")
        print(f"   唯一基础URL数: {stats['unique_base_urls']}")
        print(f"   总唯一URL数: {stats['total_unique_urls']}")
        print("=" * 50)
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        return
    
    while True:
        print("\n请选择操作:")
        print("1. 检查单个URL")
        print("2. 批量检查URL")
        print("3. 查找相似URL")
        print("4. 显示统计信息")
        print("5. 退出")
        
        choice = input("\n请输入选择 (1-5): ").strip()
        
        if choice == '1':
            # 检查单个URL
            url = input("请输入要检查的订阅URL: ").strip()
            if url:
                result = checker.check_url_exists(url)
                print(f"\n📋 检查结果:")
                print(f"   原始URL: {result['original_url']}")
                print(f"   基础URL: {result['base_url']}")
                print(f"   是否存在: {'✅ 是' if result['exists'] else '❌ 否'}")
                
                if result['exists']:
                    print(f"   在已发现列表: {'✅ 是' if result['in_discovered'] else '❌ 否'}")
                    print(f"   在已通知列表: {'✅ 是' if result['in_notified'] else '❌ 否'}")
                    if result['matched_url']:
                        print(f"   匹配的URL: {result['matched_url']}")
                else:
                    print("   🆕 这是一个新的订阅URL")
        
        elif choice == '2':
            # 批量检查URL
            print("请输入多个URL，每行一个，输入空行结束:")
            urls = []
            while True:
                url = input().strip()
                if not url:
                    break
                urls.append(url)
            
            if urls:
                results = checker.check_multiple_urls(urls)
                print(f"\n📋 批量检查结果 (共{len(urls)}个URL):")
                print("-" * 80)
                
                existing_count = 0
                for i, result in enumerate(results, 1):
                    status = "✅ 存在" if result['exists'] else "🆕 新URL"
                    if result['exists']:
                        existing_count += 1
                    print(f"{i:2d}. {status} - {result['original_url'][:60]}...")
                
                print("-" * 80)
                print(f"统计: {existing_count}/{len(urls)} 个URL已存在, {len(urls)-existing_count} 个新URL")
        
        elif choice == '3':
            # 查找相似URL
            url = input("请输入要查找相似URL的订阅地址: ").strip()
            if url:
                similar_urls = checker.find_similar_urls(url)
                print(f"\n📋 相似URL查找结果:")
                print(f"   查询URL: {url}")
                print(f"   基础URL: {checker.extract_base_subscription_url(url)}")
                
                if similar_urls:
                    print(f"   找到 {len(similar_urls)} 个相似URL:")
                    for i, similar_url in enumerate(similar_urls, 1):
                        print(f"     {i}. {similar_url}")
                else:
                    print("   🆕 没有找到相似的URL")
        
        elif choice == '4':
            # 显示统计信息
            stats = checker.get_statistics()
            print(f"\n📊 详细统计信息:")
            print(f"   已发现URL数量: {stats['discovered_count']}")
            print(f"   已通知URL数量: {stats['notified_count']}")
            print(f"   唯一基础URL数: {stats['unique_base_urls']}")
            print(f"   总唯一URL数: {stats['total_unique_urls']}")
            
            # 计算重复率
            total_urls = stats['discovered_count'] + stats['notified_count']
            if total_urls > 0:
                duplicate_rate = (total_urls - stats['total_unique_urls']) / total_urls * 100
                print(f"   重复率: {duplicate_rate:.1f}%")
        
        elif choice == '5':
            print("👋 再见！")
            break
        
        else:
            print("❌ 无效选择，请重新输入")


# 便捷函数，可以被其他脚本导入使用
def quick_check(url: str, discovered_file: str = 'discovered_urls.json', 
                notified_file: str = 'notified_urls.txt') -> bool:
    """
    快速检查URL是否存在
    
    Args:
        url: 要检查的URL
        discovered_file: 已发现URL文件
        notified_file: 已通知URL文件
        
    Returns:
        bool: 是否存在
    """
    checker = URLHistoryChecker(discovered_file, notified_file)
    result = checker.check_url_exists(url)
    return result['exists']


if __name__ == "__main__":
    main()
