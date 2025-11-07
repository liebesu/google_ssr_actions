#!/usr/bin/env python3
"""
国内本地节点速度测试工具
专为江苏等国内地区设计，测试到节点的真实速度
"""

import requests
import time
import json
import threading
import concurrent.futures
from typing import Dict, List, Optional
import socket
import subprocess
import os
import sys
from urllib.parse import urlparse

class LocalSpeedTester:
    def __init__(self, timeout: int = 10, max_workers: int = 10):
        """
        初始化本地速度测试器
        
        Args:
            timeout: 单个测试超时时间（秒）
            max_workers: 并发测试线程数
        """
        self.timeout = timeout
        self.max_workers = max_workers
        
        # 国内友好的测试目标
        self.test_urls = [
            "http://www.gstatic.com/generate_204",  # Google连通性测试
            "https://www.google.com",               # Google主页
            "https://www.youtube.com",              # YouTube
            "https://www.github.com",               # GitHub
            "https://www.cloudflare.com",           # Cloudflare
            "https://www.twitter.com",              # Twitter
            "https://www.facebook.com",             # Facebook
        ]
        
        # 国内基准测试（作为对比）
        self.china_benchmark = [
            "https://www.baidu.com",
            "https://www.qq.com",
            "https://www.taobao.com",
        ]

    def test_node_with_proxy(self, node_uri: str, proxy_config: Dict) -> Dict:
        """
        使用代理测试节点速度
        
        Args:
            node_uri: 节点URI
            proxy_config: 代理配置字典
            
        Returns:
            测试结果
        """
        result = {
            "node_uri": node_uri,
            "success": False,
            "avg_latency": None,
            "success_rate": 0.0,
            "speed_score": 0.0,
            "test_details": [],
            "error": None
        }
        
        try:
            # 创建代理会话
            session = requests.Session()
            
            # 配置代理
            if proxy_config.get("type") == "ss":
                session.proxies = {
                    'http': f'socks5://127.0.0.1:{proxy_config.get("port", 1080)}',
                    'https': f'socks5://127.0.0.1:{proxy_config.get("port", 1080)}'
                }
            elif proxy_config.get("type") == "http":
                session.proxies = {
                    'http': f'http://{proxy_config.get("server")}:{proxy_config.get("port")}',
                    'https': f'http://{proxy_config.get("server")}:{proxy_config.get("port")}'
                }
            
            # 执行速度测试
            test_results = self._run_proxy_tests(session)
            result["test_details"] = test_results
            
            if test_results:
                successful_tests = [t for t in test_results if t["success"]]
                result["success_rate"] = len(successful_tests) / len(test_results)
                
                if successful_tests:
                    result["success"] = True
                    latencies = [t["latency"] for t in successful_tests]
                    result["avg_latency"] = sum(latencies) / len(latencies)
                    result["speed_score"] = self._calculate_speed_score(
                        result["avg_latency"], 
                        result["success_rate"]
                    )
            
        except Exception as e:
            result["error"] = str(e)
        
        return result

    def _run_proxy_tests(self, session: requests.Session) -> List[Dict]:
        """
        执行代理速度测试
        """
        results = []
        
        # 设置请求头
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # 测试每个URL
        for url in self.test_urls:
            result = self._test_single_url_with_proxy(session, url)
            results.append(result)
        
        return results

    def _test_single_url_with_proxy(self, session: requests.Session, url: str) -> Dict:
        """
        使用代理测试单个URL
        """
        result = {
            "url": url,
            "success": False,
            "latency": None,
            "status_code": None,
            "error": None
        }
        
        try:
            start_time = time.time()
            response = session.get(url, timeout=self.timeout)
            end_time = time.time()
            
            result["success"] = True
            result["latency"] = (end_time - start_time) * 1000  # 毫秒
            result["status_code"] = response.status_code
            
        except requests.exceptions.Timeout:
            result["error"] = "超时"
        except requests.exceptions.ProxyError:
            result["error"] = "代理错误"
        except requests.exceptions.ConnectionError:
            result["error"] = "连接错误"
        except Exception as e:
            result["error"] = str(e)
        
        return result

    def _calculate_speed_score(self, latency: float, success_rate: float) -> float:
        """
        计算综合速度评分
        """
        if latency is None or success_rate == 0:
            return 0.0
        
        # 延迟评分（延迟越低分数越高）
        latency_score = max(0, 2000 - latency) / 20  # 0-100分
        
        # 成功率评分
        success_score = success_rate * 100  # 0-100分
        
        # 综合评分
        total_score = (latency_score * 0.7 + success_score * 0.3)
        return min(100.0, max(0.0, total_score))

    def test_nodes_batch(self, node_configs: List[Dict]) -> List[Dict]:
        """
        批量测试节点速度
        """
        results = []
        
        print(f"🚀 开始测试 {len(node_configs)} 个节点...")
        print(f"⏱️ 超时设置: {self.timeout}秒")
        print(f"🔢 并发数: {self.max_workers}")
        print("-" * 60)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_config = {
                executor.submit(self.test_node_with_proxy, config["uri"], config): config 
                for config in node_configs
            }
            
            completed = 0
            for future in concurrent.futures.as_completed(future_to_config):
                config = future_to_config[future]
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1
                    
                    if result["success"]:
                        print(f"✅ [{completed:2d}/{len(node_configs)}] {result['avg_latency']:6.1f}ms (评分: {result['speed_score']:5.1f}) - {config['name']}")
                    else:
                        print(f"❌ [{completed:2d}/{len(node_configs)}] 失败 - {config['name']}")
                        
                except Exception as e:
                    results.append({
                        "node_uri": config["uri"],
                        "success": False,
                        "error": str(e)
                    })
                    completed += 1
                    print(f"❌ [{completed:2d}/{len(node_configs)}] 异常 - {config['name']}")
        
        return results

    def generate_report(self, results: List[Dict]) -> Dict:
        """
        生成测试报告
        """
        successful_results = [r for r in results if r.get("success", False)]
        
        if not successful_results:
            return {
                "total_nodes": len(results),
                "successful_nodes": 0,
                "success_rate": 0.0,
                "fastest_node": None,
                "speed_distribution": {},
                "ranking": []
            }
        
        # 按综合评分排序
        sorted_results = sorted(successful_results, key=lambda x: x.get("speed_score", 0), reverse=True)
        
        # 统计速度分布
        speed_distribution = {}
        for result in successful_results:
            score = result.get("speed_score", 0)
            if score >= 80:
                grade = "A"
            elif score >= 60:
                grade = "B"
            elif score >= 40:
                grade = "C"
            elif score >= 20:
                grade = "D"
            else:
                grade = "F"
            speed_distribution[grade] = speed_distribution.get(grade, 0) + 1
        
        # 计算平均延迟
        latencies = [r.get("avg_latency") for r in successful_results if r.get("avg_latency")]
        avg_latency = sum(latencies) / len(latencies) if latencies else None
        
        report = {
            "total_nodes": len(results),
            "successful_nodes": len(successful_results),
            "success_rate": len(successful_results) / len(results) * 100,
            "avg_latency": avg_latency,
            "fastest_node": sorted_results[0] if sorted_results else None,
            "slowest_node": sorted_results[-1] if sorted_results else None,
            "speed_distribution": speed_distribution,
            "ranking": sorted_results
        }
        
        return report

    def print_report(self, report: Dict):
        """
        打印测试报告
        """
        print("\n" + "="*70)
        print("📊 国内节点速度测试报告")
        print("="*70)
        
        print(f"总节点数: {report['total_nodes']}")
        print(f"成功测试: {report['successful_nodes']}")
        print(f"成功率: {report['success_rate']:.1f}%")
        
        if report['avg_latency']:
            print(f"平均延迟: {report['avg_latency']:.1f}ms")
        
        if report['fastest_node']:
            fastest = report['fastest_node']
            print(f"最快节点: {fastest['avg_latency']:.1f}ms (评分: {fastest['speed_score']:.1f})")
        
        # 速度分布
        print(f"\n📈 速度分布:")
        for grade in ['A', 'B', 'C', 'D', 'F']:
            count = report['speed_distribution'].get(grade, 0)
            if count > 0:
                print(f"  {grade}级: {count} 个节点")
        
        print(f"\n🏆 速度排行榜 (前10名):")
        print("-" * 70)
        for i, node in enumerate(report['ranking'][:10], 1):
            uri_short = node['node_uri'][:45] + "..." if len(node['node_uri']) > 45 else node['node_uri']
            print(f"{i:2d}. {node['avg_latency']:6.1f}ms (评分: {node['speed_score']:5.1f}) - {uri_short}")
        
        print("="*70)

    def save_results(self, results: List[Dict], report: Dict, filename_prefix: str = None):
        """
        保存测试结果
        """
        if not filename_prefix:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename_prefix = f"local_speed_test_{timestamp}"
        
        # 保存详细结果
        results_file = f"{filename_prefix}_results.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # 保存报告
        report_file = f"{filename_prefix}_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 结果已保存:")
        print(f"  - {results_file} (详细结果)")
        print(f"  - {report_file} (测试报告)")

def main():
    """
    主函数 - 示例用法
    """
    print("🇨🇳 国内节点速度测试工具")
    print("专为江苏等国内地区设计")
    print("-" * 50)
    
    # 示例节点配置（需要根据实际情况修改）
    sample_nodes = [
        {
            "name": "节点1",
            "uri": "ss://YWVzLTI1Ni1nY206cGFzc3dvcmQ@server1.example.com:443#测试节点1",
            "type": "ss",
            "server": "server1.example.com",
            "port": 443
        },
        {
            "name": "节点2", 
            "uri": "trojan://password@server2.example.com:443#测试节点2",
            "type": "trojan",
            "server": "server2.example.com",
            "port": 443
        }
    ]
    
    # 创建测试器
    tester = LocalSpeedTester(timeout=15, max_workers=5)
    
    # 执行测试
    results = tester.test_nodes_batch(sample_nodes)
    
    # 生成报告
    report = tester.generate_report(results)
    
    # 打印报告
    tester.print_report(report)
    
    # 保存结果
    tester.save_results(results, report)
    
    return results, report

if __name__ == "__main__":
    main()




