#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据清理工具
清理和验证项目中的URL数据文件
"""

import json
import os
import re
from typing import List, Set, Dict
from urllib.parse import urlparse


class DataCleaner:
    """数据清理器"""
    
    def __init__(self):
        self.valid_url_pattern = re.compile(r'^https?://[^\s"\'<>]+api/v1/client/subscribe\?token=[A-Za-z0-9]+')
        self.placeholder_patterns = [
            r'your-provider\.com',
            r'xxxxx',
            r'xxxxxxxx',
            r'example\.com',
            r'test\.com'
        ]
    
    def is_valid_subscription_url(self, url: str) -> bool:
        """检查是否为有效的订阅URL"""
        if not isinstance(url, str):
            return False
        
        # 基本格式检查
        if not self.valid_url_pattern.match(url):
            return False
        
        # 检查是否为占位符URL
        for pattern in self.placeholder_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False
        
        # URL解析检查
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # 检查是否包含必要的token参数
            if 'token=' not in parsed.query:
                return False
            
            return True
        except Exception:
            return False
    
    def normalize_url(self, url: str) -> str:
        """标准化URL"""
        # 移除尾部的额外信息
        url = re.sub(r'订阅流量：[^&]*', '', url)
        url = re.sub(r'总流量:[^&]*', '', url)
        url = re.sub(r'剩余流量:[^&]*', '', url)
        url = re.sub(r'已上传:[^&]*', '', url)
        url = re.sub(r'已下载:[^&]*', '', url)
        url = re.sub(r'该订阅将于[^&]*', '', url)
        
        return url.strip()
    
    def clean_url_list(self, urls: List) -> List[str]:
        """清理URL列表"""
        clean_urls = set()
        
        for item in urls:
            # 跳过非字符串项
            if not isinstance(item, str):
                continue
            
            # 跳过明显的非URL项
            if not item.startswith(('http://', 'https://')):
                continue
            
            # 标准化URL
            normalized_url = self.normalize_url(item)
            
            # 验证URL
            if self.is_valid_subscription_url(normalized_url):
                clean_urls.add(normalized_url)
        
        return sorted(list(clean_urls))
    
    def clean_discovered_urls_file(self, file_path: str) -> Dict:
        """清理discovered_urls.json文件"""
        print(f"正在清理文件: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            original_count = len(data)
            print(f"原始条目数: {original_count}")
            
            # 清理数据
            clean_urls = self.clean_url_list(data)
            
            print(f"清理后URL数: {len(clean_urls)}")
            print(f"移除条目数: {original_count - len(clean_urls)}")
            
            # 备份原文件
            backup_path = file_path + '.backup'
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"原文件已备份到: {backup_path}")
            
            # 写入清理后的数据
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(clean_urls, f, ensure_ascii=False, indent=2)
            
            return {
                'original_count': original_count,
                'clean_count': len(clean_urls),
                'removed_count': original_count - len(clean_urls),
                'backup_path': backup_path
            }
            
        except Exception as e:
            print(f"清理文件失败: {e}")
            return {'error': str(e)}
    
    def validate_data_files(self, base_dir: str = '.') -> Dict:
        """验证项目中的数据文件"""
        results = {}
        
        files_to_check = [
            'discovered_urls.json',
            'api_urls_results.json',
            'data/history_urls.json',
            'data/live_urls.json'
        ]
        
        for file_path in files_to_check:
            full_path = os.path.join(base_dir, file_path)
            if os.path.exists(full_path):
                print(f"\n检查文件: {file_path}")
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    if isinstance(data, list):
                        valid_urls = [item for item in data if isinstance(item, str) and self.is_valid_subscription_url(item)]
                        invalid_items = [item for item in data if not (isinstance(item, str) and self.is_valid_subscription_url(item))]
                        
                        results[file_path] = {
                            'total_items': len(data),
                            'valid_urls': len(valid_urls),
                            'invalid_items': len(invalid_items),
                            'invalid_examples': invalid_items[:5] if invalid_items else []
                        }
                        
                        print(f"  总条目: {len(data)}")
                        print(f"  有效URL: {len(valid_urls)}")
                        print(f"  无效条目: {len(invalid_items)}")
                        if invalid_items:
                            print(f"  无效示例: {invalid_items[:3]}")
                    
                    elif isinstance(data, dict):
                        # 处理字典格式的文件（如api_urls_results.json）
                        urls = data.get('urls', [])
                        if urls:
                            valid_urls = [url for url in urls if self.is_valid_subscription_url(url)]
                            results[file_path] = {
                                'total_items': len(urls),
                                'valid_urls': len(valid_urls),
                                'invalid_items': len(urls) - len(valid_urls)
                            }
                            print(f"  总URL: {len(urls)}")
                            print(f"  有效URL: {len(valid_urls)}")
                        else:
                            results[file_path] = {'note': 'No URLs found in dict'}
                    
                except Exception as e:
                    results[file_path] = {'error': str(e)}
                    print(f"  错误: {e}")
            else:
                results[file_path] = {'status': 'file_not_found'}
                print(f"  文件不存在: {file_path}")
        
        return results


def main():
    """主函数"""
    print("🧹 数据清理工具")
    print("=" * 50)
    
    cleaner = DataCleaner()
    
    # 验证数据文件
    print("\n📊 验证数据文件...")
    results = cleaner.validate_data_files()
    
    # 清理discovered_urls.json
    print("\n🔧 清理discovered_urls.json...")
    if os.path.exists('discovered_urls.json'):
        clean_result = cleaner.clean_discovered_urls_file('discovered_urls.json')
        if 'error' not in clean_result:
            print("✅ 清理完成")
            print(f"   原始条目: {clean_result['original_count']}")
            print(f"   清理后: {clean_result['clean_count']}")
            print(f"   移除: {clean_result['removed_count']}")
        else:
            print(f"❌ 清理失败: {clean_result['error']}")
    else:
        print("⚠️ discovered_urls.json 文件不存在")
    
    print("\n✅ 数据清理完成")


if __name__ == "__main__":
    main()

