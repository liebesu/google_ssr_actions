#!/usr/bin/env python3
"""
快速节点速度测试工具
适合国内用户快速测试节点速度
"""

import requests
import time
import json
from typing import List, Dict

class QuickSpeedTest:
    def __init__(self):
        self.test_urls = [
            "http://www.gstatic.com/generate_204",
            "https://www.google.com",
            "https://www.youtube.com",
        ]
    
    def test_single_node(self, node_name: str, proxy_url: str) -> Dict:
        """
        测试单个节点速度
        
        Args:
            node_name: 节点名称
            proxy_url: 代理URL (如: socks5://127.0.0.1:1080)
        """
        result = {
            "name": node_name,
            "success": False,
            "avg_latency": None,
            "success_rate": 0.0,
            "error": None
        }
        
        try:
            # 创建会话
            session = requests.Session()
            session.proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            # 测试每个URL
            latencies = []
            success_count = 0
            
            for url in self.test_urls:
                try:
                    start_time = time.time()
                    response = session.get(url, timeout=10)
                    end_time = time.time()
                    
                    if response.status_code in [200, 204]:
                        latency = (end_time - start_time) * 1000
                        latencies.append(latency)
                        success_count += 1
                        print(f"  ✅ {url}: {latency:.1f}ms")
                    else:
                        print(f"  ❌ {url}: HTTP {response.status_code}")
                        
                except Exception as e:
                    print(f"  ❌ {url}: {str(e)}")
            
            # 计算结果
            if latencies:
                result["success"] = True
                result["avg_latency"] = sum(latencies) / len(latencies)
                result["success_rate"] = success_count / len(self.test_urls)
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def test_nodes(self, nodes: List[Dict]) -> List[Dict]:
        """
        测试多个节点
        """
        results = []
        
        print(f"🚀 开始测试 {len(nodes)} 个节点...")
        print("=" * 60)
        
        for i, node in enumerate(nodes, 1):
            print(f"\n[{i}/{len(nodes)}] 测试节点: {node['name']}")
            print(f"代理: {node['proxy']}")
            
            result = self.test_single_node(node['name'], node['proxy'])
            results.append(result)
            
            if result["success"]:
                print(f"✅ 平均延迟: {result['avg_latency']:.1f}ms")
                print(f"✅ 成功率: {result['success_rate']*100:.1f}%")
            else:
                print(f"❌ 测试失败: {result['error']}")
        
        return results
    
    def print_ranking(self, results: List[Dict]):
        """
        打印速度排行
        """
        successful_results = [r for r in results if r.get("success", False)]
        
        if not successful_results:
            print("\n❌ 没有成功的测试结果")
            return
        
        # 按延迟排序
        sorted_results = sorted(successful_results, key=lambda x: x.get("avg_latency", float('inf')))
        
        print("\n" + "="*60)
        print("🏆 速度排行榜")
        print("="*60)
        
        for i, node in enumerate(sorted_results, 1):
            latency = node['avg_latency']
            success_rate = node['success_rate'] * 100
            
            # 评级
            if latency < 100:
                grade = "A"
            elif latency < 200:
                grade = "B"
            elif latency < 500:
                grade = "C"
            else:
                grade = "D"
            
            print(f"{i:2d}. {node['name']:20s} {latency:6.1f}ms [{grade}] 成功率: {success_rate:5.1f}%")
        
        print("="*60)

def main():
    """
    主函数 - 使用示例
    """
    print("🇨🇳 快速节点速度测试工具")
    print("专为国内用户设计")
    print("-" * 50)
    
    # 配置你的节点（需要根据实际情况修改）
    nodes = [
        {
            "name": "香港节点1",
            "proxy": "socks5://127.0.0.1:1080"  # 你的代理地址
        },
        {
            "name": "美国节点1", 
            "proxy": "socks5://127.0.0.1:1081"  # 你的代理地址
        },
        {
            "name": "日本节点1",
            "proxy": "socks5://127.0.0.1:1082"  # 你的代理地址
        }
    ]
    
    # 创建测试器
    tester = QuickSpeedTest()
    
    # 执行测试
    results = tester.test_nodes(nodes)
    
    # 显示排行
    tester.print_ranking(results)
    
    # 保存结果
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"speed_test_results_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 测试结果已保存到: {filename}")

if __name__ == "__main__":
    main()




