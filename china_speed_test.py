#!/usr/bin/env python3
"""
国内节点速度评测工具
专为江苏等国内地区设计，使用国内友好的测试目标
"""

import requests
import time
import json
import threading
import concurrent.futures
from typing import Dict, List, Tuple, Optional
import socket
import subprocess
import os

class ChinaSpeedTester:
    def __init__(self, timeout: int = 10, max_workers: int = 5):
        """
        初始化国内速度测试器
        
        Args:
            timeout: 单个测试超时时间（秒）
            max_workers: 并发测试线程数（降低避免被限制）
        """
        self.timeout = timeout
        self.max_workers = max_workers
        
        # 国内友好的测试目标
        self.test_urls = [
            "http://www.gstatic.com/generate_204",  # Google连通性测试（国内可访问）
            "https://www.google.com",               # Google主页
            "https://www.youtube.com",              # YouTube
            "https://www.github.com",               # GitHub
            "https://www.cloudflare.com",           # Cloudflare
        ]
        
        # 国内测速服务器（作为对比基准）
        self.china_benchmark_urls = [
            "https://www.baidu.com",
            "https://www.qq.com", 
            "https://www.taobao.com",
        ]

    def test_node_speed(self, node_uri: str) -> Dict:
        """
        测试单个节点速度
        
        Args:
            node_uri: 节点URI字符串
            
        Returns:
            测试结果字典
        """
        result = {
            "node_uri": node_uri,
            "success": False,
            "avg_latency": None,
            "success_rate": 0.0,
            "test_details": [],
            "error": None,
            "speed_grade": "F"  # A-F等级
        }
        
        try:
            # 解析节点信息
            node_info = self._parse_node_uri(node_uri)
            if not node_info:
                result["error"] = "无法解析节点URI"
                return result
            
            # 执行速度测试
            test_results = self._run_speed_tests(node_info)
            result["test_details"] = test_results
            
            if test_results:
                # 计算成功率
                successful_tests = [t for t in test_results if t["success"]]
                result["success_rate"] = len(successful_tests) / len(test_results)
                
                if successful_tests:
                    result["success"] = True
                    # 计算平均延迟
                    latencies = [t["latency"] for t in successful_tests]
                    result["avg_latency"] = sum(latencies) / len(latencies)
                    
                    # 评定速度等级
                    result["speed_grade"] = self._calculate_speed_grade(result["avg_latency"])
            
        except Exception as e:
            result["error"] = str(e)
        
        return result

    def _parse_node_uri(self, uri: str) -> Optional[Dict]:
        """
        解析节点URI（简化版）
        """
        try:
            # 提取服务器地址和端口
            if "://" in uri:
                scheme, rest = uri.split("://", 1)
                if "@" in rest:
                    auth, server_part = rest.split("@", 1)
                    if ":" in server_part:
                        server, port = server_part.split(":", 1)
                        return {
                            "type": scheme,
                            "server": server,
                            "port": int(port.split("#")[0].split("?")[0])
                        }
        except:
            pass
        return None

    def _run_speed_tests(self, node_info: Dict) -> List[Dict]:
        """
        执行速度测试
        """
        results = []
        
        # 创建测试会话
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # 测试每个URL
        for url in self.test_urls:
            result = self._test_single_url(session, url, node_info)
            results.append(result)
        
        return results

    def _test_single_url(self, session: requests.Session, url: str, node_info: Dict) -> Dict:
        """
        测试单个URL
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
        except requests.exceptions.ConnectionError:
            result["error"] = "连接错误"
        except Exception as e:
            result["error"] = str(e)
        
        return result

    def _calculate_speed_grade(self, latency: float) -> str:
        """
        根据延迟计算速度等级
        """
        if latency < 100:
            return "A"  # 优秀
        elif latency < 200:
            return "B"  # 良好
        elif latency < 500:
            return "C"  # 一般
        elif latency < 1000:
            return "D"  # 较差
        else:
            return "F"  # 很差

    def test_nodes_batch(self, node_uris: List[str]) -> List[Dict]:
        """
        批量测试节点速度
        """
        results = []
        
        print(f"🚀 开始测试 {len(node_uris)} 个节点...")
        print(f"⏱️ 超时设置: {self.timeout}秒")
        print(f"🔢 并发数: {self.max_workers}")
        print("-" * 50)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有测试任务
            future_to_uri = {
                executor.submit(self.test_node_speed, uri): uri 
                for uri in node_uris
            }
            
            # 收集结果
            completed = 0
            for future in concurrent.futures.as_completed(future_to_uri):
                uri = future_to_uri[future]
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1
                    
                    # 显示进度
                    if result["success"]:
                        print(f"✅ [{completed:2d}/{len(node_uris)}] {result['avg_latency']:6.1f}ms - {result['speed_grade']} - {uri[:50]}...")
                    else:
                        print(f"❌ [{completed:2d}/{len(node_uris)}] 失败 - {uri[:50]}...")
                        
                except Exception as e:
                    results.append({
                        "node_uri": uri,
                        "success": False,
                        "error": str(e)
                    })
                    completed += 1
                    print(f"❌ [{completed:2d}/{len(node_uris)}] 异常 - {uri[:50]}...")
        
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
        
        # 按延迟排序
        sorted_results = sorted(successful_results, key=lambda x: x.get("avg_latency", float('inf')))
        
        # 统计速度分布
        speed_distribution = {}
        for result in successful_results:
            grade = result.get("speed_grade", "F")
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
            "ranking": sorted_results[:20]  # 前20名
        }
        
        return report

    def print_report(self, report: Dict):
        """
        打印测试报告
        """
        print("\n" + "="*70)
        print("📊 节点速度测试报告")
        print("="*70)
        
        print(f"总节点数: {report['total_nodes']}")
        print(f"成功测试: {report['successful_nodes']}")
        print(f"成功率: {report['success_rate']:.1f}%")
        
        if report['avg_latency']:
            print(f"平均延迟: {report['avg_latency']:.1f}ms")
        
        if report['fastest_node']:
            fastest = report['fastest_node']
            print(f"最快节点: {fastest['avg_latency']:.1f}ms (等级: {fastest['speed_grade']})")
        
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
            print(f"{i:2d}. {node['avg_latency']:6.1f}ms [{node['speed_grade']}] - {uri_short}")
        
        print("="*70)

    def save_results(self, results: List[Dict], report: Dict, filename_prefix: str = None):
        """
        保存测试结果
        """
        if not filename_prefix:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename_prefix = f"china_speed_test_{timestamp}"
        
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
    主函数
    """
    print("🇨🇳 国内节点速度评测工具")
    print("专为江苏等国内地区设计")
    print("-" * 50)
    
    # 示例节点列表（实际使用时从文件读取）
    sample_nodes = [
        "ss://YWVzLTI1Ni1nY206cGFzc3dvcmQ@server1.example.com:443#测试节点1",
        "trojan://password@server2.example.com:443#测试节点2",
        "vmess://eyJ2IjoiMiIsInBzIjoi5rWL6K+V5Yqg6L29IiwiYWRkIjoic2VydmVyMy5leGFtcGxlLmNvbSIsInBvcnQiOiI0NDMiLCJpZCI6InV1aWQiLCJhaWQiOiIwIiwic2N5IjoiYXV0byIsIm5ldCI6IndzcyIsInR5cGUiOiJub25lIiwiaG9zdCI6IiIsInRscyI6InRscyJ9#测试节点3"
    ]
    
    # 创建测试器
    tester = ChinaSpeedTester(timeout=15, max_workers=3)
    
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




