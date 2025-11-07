#!/usr/bin/env python3
"""
节点速度评测工具
适用于国内江苏地区，通过多种方式评测节点速度
"""

import requests
import time
import json
import threading
import concurrent.futures
from typing import Dict, List, Tuple, Optional
from urllib.parse import urlparse
import socket
import subprocess
import os
import sys

class SpeedTester:
    def __init__(self, timeout: int = 10, max_workers: int = 20):
        """
        初始化速度测试器
        
        Args:
            timeout: 单个测试超时时间（秒）
            max_workers: 并发测试线程数
        """
        self.timeout = timeout
        self.max_workers = max_workers
        
        # 测试目标网站（适合国内访问）
        self.test_urls = [
            "http://www.gstatic.com/generate_204",  # Google连通性测试
            "https://www.google.com",               # Google主页
            "https://www.youtube.com",              # YouTube
            "https://www.twitter.com",              # Twitter
            "https://www.facebook.com",             # Facebook
            "https://www.instagram.com",            # Instagram
            "https://www.github.com",               # GitHub
            "https://www.cloudflare.com",           # Cloudflare
        ]
        
        # 国内测速服务器
        self.china_test_servers = [
            "http://www.baidu.com",
            "https://www.qq.com",
            "https://www.taobao.com",
            "https://www.jd.com",
        ]

    def test_single_node(self, node_uri: str, proxy_config: Optional[Dict] = None) -> Dict:
        """
        测试单个节点的速度
        
        Args:
            node_uri: 节点URI
            proxy_config: 代理配置
            
        Returns:
            测试结果字典
        """
        result = {
            "node_uri": node_uri,
            "success": False,
            "avg_latency": None,
            "success_rate": 0.0,
            "test_results": [],
            "error": None
        }
        
        try:
            # 解析节点URI获取代理配置
            if not proxy_config:
                proxy_config = self._parse_node_uri(node_uri)
            
            if not proxy_config:
                result["error"] = "无法解析节点URI"
                return result
            
            # 执行速度测试
            test_results = self._run_speed_tests(proxy_config)
            
            if test_results:
                result["test_results"] = test_results
                result["success"] = True
                
                # 计算平均延迟
                latencies = [t["latency"] for t in test_results if t["success"]]
                if latencies:
                    result["avg_latency"] = sum(latencies) / len(latencies)
                    result["success_rate"] = len(latencies) / len(test_results)
            
        except Exception as e:
            result["error"] = str(e)
        
        return result

    def _parse_node_uri(self, uri: str) -> Optional[Dict]:
        """
        解析节点URI为代理配置
        支持SS、Trojan、VMess、VLESS等协议
        """
        try:
            from urllib.parse import urlparse, parse_qs
            
            parsed = urlparse(uri)
            scheme = parsed.scheme.lower()
            
            if scheme == "ss":
                return self._parse_ss_uri(parsed)
            elif scheme == "trojan":
                return self._parse_trojan_uri(parsed)
            elif scheme in ["vmess", "vless"]:
                return self._parse_vmess_uri(parsed)
            else:
                return None
                
        except Exception:
            return None

    def _parse_ss_uri(self, parsed) -> Dict:
        """解析SS URI"""
        # 简化实现，实际需要base64解码
        return {
            "type": "ss",
            "server": parsed.hostname,
            "port": parsed.port or 443,
            "method": "aes-256-gcm",  # 默认方法
            "password": "password"    # 需要从URI中解析
        }

    def _parse_trojan_uri(self, parsed) -> Dict:
        """解析Trojan URI"""
        return {
            "type": "trojan",
            "server": parsed.hostname,
            "port": parsed.port or 443,
            "password": parsed.username or "password"
        }

    def _parse_vmess_uri(self, parsed) -> Dict:
        """解析VMess/VLESS URI"""
        return {
            "type": "vmess",
            "server": parsed.hostname,
            "port": parsed.port or 443,
            "uuid": "uuid",  # 需要从URI中解析
            "alterId": 0
        }

    def _run_speed_tests(self, proxy_config: Dict) -> List[Dict]:
        """
        执行速度测试
        """
        results = []
        
        # 创建会话
        session = requests.Session()
        
        # 配置代理
        if proxy_config["type"] == "ss":
            session.proxies = {
                'http': f'socks5://127.0.0.1:1080',
                'https': f'socks5://127.0.0.1:1080'
            }
        elif proxy_config["type"] == "trojan":
            session.proxies = {
                'http': f'http://127.0.0.1:8080',
                'https': f'http://127.0.0.1:8080'
            }
        
        # 测试每个URL
        for url in self.test_urls:
            result = self._test_single_url(session, url)
            results.append(result)
        
        return results

    def _test_single_url(self, session: requests.Session, url: str) -> Dict:
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
            result["latency"] = (end_time - start_time) * 1000  # 转换为毫秒
            result["status_code"] = response.status_code
            
        except requests.exceptions.Timeout:
            result["error"] = "超时"
        except requests.exceptions.ConnectionError:
            result["error"] = "连接错误"
        except Exception as e:
            result["error"] = str(e)
        
        return result

    def test_nodes_batch(self, node_uris: List[str]) -> List[Dict]:
        """
        批量测试节点速度
        """
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有测试任务
            future_to_uri = {
                executor.submit(self.test_single_node, uri): uri 
                for uri in node_uris
            }
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_uri):
                uri = future_to_uri[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({
                        "node_uri": uri,
                        "success": False,
                        "error": str(e)
                    })
        
        return results

    def ping_test(self, host: str, count: int = 4) -> Dict:
        """
        Ping测试（适用于服务器IP）
        """
        result = {
            "host": host,
            "success": False,
            "avg_latency": None,
            "packet_loss": 100.0,
            "raw_output": ""
        }
        
        try:
            # 执行ping命令
            cmd = ["ping", "-c", str(count), host]
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            result["raw_output"] = process.stdout
            
            if process.returncode == 0:
                result["success"] = True
                # 解析ping结果（简化版）
                lines = process.stdout.split('\n')
                for line in lines:
                    if 'avg' in line.lower():
                        # 提取平均延迟
                        parts = line.split('/')
                        if len(parts) >= 5:
                            result["avg_latency"] = float(parts[4])
                    elif 'packet loss' in line.lower():
                        # 提取丢包率
                        if '%' in line:
                            loss_str = line.split('%')[0].split()[-1]
                            result["packet_loss"] = float(loss_str)
            
        except subprocess.TimeoutExpired:
            result["error"] = "Ping超时"
        except Exception as e:
            result["error"] = str(e)
        
        return result

    def tcp_connect_test(self, host: str, port: int, timeout: int = 5) -> Dict:
        """
        TCP连接测试
        """
        result = {
            "host": host,
            "port": port,
            "success": False,
            "latency": None,
            "error": None
        }
        
        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            end_time = time.time()
            sock.close()
            
            result["success"] = True
            result["latency"] = (end_time - start_time) * 1000
            
        except socket.timeout:
            result["error"] = "连接超时"
        except socket.error as e:
            result["error"] = f"连接错误: {e}"
        except Exception as e:
            result["error"] = str(e)
        
        return result

    def generate_speed_report(self, results: List[Dict]) -> Dict:
        """
        生成速度测试报告
        """
        successful_results = [r for r in results if r.get("success", False)]
        
        if not successful_results:
            return {
                "total_nodes": len(results),
                "successful_nodes": 0,
                "success_rate": 0.0,
                "fastest_node": None,
                "slowest_node": None,
                "avg_latency": None,
                "ranking": []
            }
        
        # 按延迟排序
        sorted_results = sorted(successful_results, key=lambda x: x.get("avg_latency", float('inf')))
        
        latencies = [r.get("avg_latency") for r in successful_results if r.get("avg_latency")]
        
        report = {
            "total_nodes": len(results),
            "successful_nodes": len(successful_results),
            "success_rate": len(successful_results) / len(results) * 100,
            "fastest_node": sorted_results[0] if sorted_results else None,
            "slowest_node": sorted_results[-1] if sorted_results else None,
            "avg_latency": sum(latencies) / len(latencies) if latencies else None,
            "ranking": sorted_results[:10]  # 前10名
        }
        
        return report

    def save_results(self, results: List[Dict], filename: str = None):
        """
        保存测试结果到文件
        """
        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"speed_test_results_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"测试结果已保存到: {filename}")

def main():
    """
    主函数 - 示例用法
    """
    # 示例节点URI列表
    test_nodes = [
        "ss://YWVzLTI1Ni1nY206cGFzc3dvcmQ@server1.example.com:443#测试节点1",
        "trojan://password@server2.example.com:443#测试节点2",
        "vmess://eyJ2IjoiMiIsInBzIjoi5rWL6K+V5Yqg6L29IiwiYWRkIjoic2VydmVyMy5leGFtcGxlLmNvbSIsInBvcnQiOiI0NDMiLCJpZCI6InV1aWQiLCJhaWQiOiIwIiwic2N5IjoiYXV0byIsIm5ldCI6IndzcyIsInR5cGUiOiJub25lIiwiaG9zdCI6IiIsInRscyI6InRscyJ9#测试节点3"
    ]
    
    # 创建测试器
    tester = SpeedTester(timeout=10, max_workers=10)
    
    print("🚀 开始节点速度测试...")
    print(f"测试节点数量: {len(test_nodes)}")
    print(f"测试目标: {len(tester.test_urls)} 个网站")
    print(f"并发数: {tester.max_workers}")
    print("-" * 50)
    
    # 执行批量测试
    results = tester.test_nodes_batch(test_nodes)
    
    # 生成报告
    report = tester.generate_speed_report(results)
    
    # 打印结果
    print("\n📊 测试报告:")
    print(f"总节点数: {report['total_nodes']}")
    print(f"成功节点数: {report['successful_nodes']}")
    print(f"成功率: {report['success_rate']:.1f}%")
    
    if report['avg_latency']:
        print(f"平均延迟: {report['avg_latency']:.1f}ms")
    
    if report['fastest_node']:
        print(f"最快节点: {report['fastest_node']['node_uri']} ({report['fastest_node']['avg_latency']:.1f}ms)")
    
    print("\n🏆 速度排行榜 (前5名):")
    for i, node in enumerate(report['ranking'][:5], 1):
        print(f"{i}. {node['node_uri']} - {node['avg_latency']:.1f}ms")
    
    # 保存结果
    tester.save_results(results)
    
    return results, report

if __name__ == "__main__":
    main()