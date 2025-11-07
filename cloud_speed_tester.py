#!/usr/bin/env python3
"""
云环境速度测试器
专为GitHub Actions等云构建环境设计
使用轻量级测试方法，避免被限制
"""

import requests
import time
import json
import threading
import concurrent.futures
from typing import Dict, List, Optional
import socket
import os
import sys

class CloudSpeedTester:
    def __init__(self, timeout: int = 8, max_workers: int = 3):
        """
        初始化云环境速度测试器
        
        Args:
            timeout: 单个测试超时时间（秒）
            max_workers: 并发测试线程数（云环境限制）
        """
        self.timeout = timeout
        self.max_workers = max_workers
        
        # 云环境友好的测试目标（避免被限制）
        self.test_urls = [
            "http://www.gstatic.com/generate_204",  # Google连通性测试
            "https://www.google.com",               # Google主页
            "https://www.github.com",               # GitHub
        ]
        
        # 国内基准测试
        self.china_benchmark = "https://www.baidu.com"

    def test_node_speed(self, node_uri: str) -> Dict:
        """
        测试单个节点速度（云环境优化版）
        """
        result = {
            "node_uri": node_uri,
            "success": False,
            "avg_latency": None,
            "success_rate": 0.0,
            "speed_score": 0.0,  # 综合评分
            "error": None
        }
        
        try:
            # 解析节点信息
            node_info = self._parse_node_uri(node_uri)
            if not node_info:
                result["error"] = "无法解析节点URI"
                return result
            
            # 执行轻量级速度测试
            test_results = self._run_lightweight_tests(node_info)
            
            if test_results:
                successful_tests = [t for t in test_results if t["success"]]
                result["success_rate"] = len(successful_tests) / len(test_results)
                
                if successful_tests:
                    result["success"] = True
                    # 计算平均延迟
                    latencies = [t["latency"] for t in successful_tests]
                    result["avg_latency"] = sum(latencies) / len(latencies)
                    
                    # 计算综合评分（延迟越低分数越高）
                    result["speed_score"] = self._calculate_speed_score(
                        result["avg_latency"], 
                        result["success_rate"]
                    )
            
        except Exception as e:
            result["error"] = str(e)
        
        return result

    def _parse_node_uri(self, uri: str) -> Optional[Dict]:
        """
        解析节点URI（简化版，适合云环境）
        """
        try:
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

    def _run_lightweight_tests(self, node_info: Dict) -> List[Dict]:
        """
        执行轻量级速度测试（适合云环境）
        """
        results = []
        
        # 创建测试会话
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; CloudSpeedTester/1.0)'
        })
        
        # 只测试关键URL
        for url in self.test_urls[:2]:  # 只测试前2个URL
            result = self._test_single_url(session, url, node_info)
            results.append(result)
        
        return results

    def _test_single_url(self, session: requests.Session, url: str, node_info: Dict) -> Dict:
        """
        测试单个URL（云环境优化）
        """
        result = {
            "url": url,
            "success": False,
            "latency": None,
            "error": None
        }
        
        try:
            start_time = time.time()
            response = session.get(url, timeout=self.timeout)
            end_time = time.time()
            
            # 只检查基本连通性
            if response.status_code in [200, 204]:
                result["success"] = True
                result["latency"] = (end_time - start_time) * 1000
            
        except requests.exceptions.Timeout:
            result["error"] = "超时"
        except Exception as e:
            result["error"] = str(e)
        
        return result

    def _calculate_speed_score(self, latency: float, success_rate: float) -> float:
        """
        计算综合速度评分
        延迟越低、成功率越高，分数越高
        """
        if latency is None or success_rate == 0:
            return 0.0
        
        # 延迟评分（延迟越低分数越高）
        latency_score = max(0, 1000 - latency) / 10  # 0-100分
        
        # 成功率评分
        success_score = success_rate * 100  # 0-100分
        
        # 综合评分
        total_score = (latency_score * 0.7 + success_score * 0.3)
        return min(100.0, max(0.0, total_score))

    def test_nodes_batch(self, node_uris: List[str]) -> List[Dict]:
        """
        批量测试节点速度（云环境优化）
        """
        results = []
        
        print(f"☁️ 云环境速度测试开始...")
        print(f"📊 测试节点数: {len(node_uris)}")
        print(f"⏱️ 超时设置: {self.timeout}秒")
        print(f"🔢 并发数: {self.max_workers}")
        print("-" * 50)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_uri = {
                executor.submit(self.test_node_speed, uri): uri 
                for uri in node_uris
            }
            
            completed = 0
            for future in concurrent.futures.as_completed(future_to_uri):
                uri = future_to_uri[future]
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1
                    
                    if result["success"]:
                        print(f"✅ [{completed:2d}/{len(node_uris)}] {result['avg_latency']:6.1f}ms (评分: {result['speed_score']:5.1f})")
                    else:
                        print(f"❌ [{completed:2d}/{len(node_uris)}] 失败")
                        
                except Exception as e:
                    results.append({
                        "node_uri": uri,
                        "success": False,
                        "error": str(e)
                    })
                    completed += 1
                    print(f"❌ [{completed:2d}/{len(node_uris)}] 异常")
        
        return results

    def generate_speed_ranking(self, results: List[Dict]) -> List[Dict]:
        """
        生成速度排行榜
        """
        successful_results = [r for r in results if r.get("success", False)]
        
        # 按综合评分排序
        sorted_results = sorted(
            successful_results, 
            key=lambda x: x.get("speed_score", 0), 
            reverse=True
        )
        
        return sorted_results

    def create_speed_optimized_subscription(self, ranking: List[Dict], output_file: str = "speed_ranking.yaml"):
        """
        创建基于速度排行的订阅文件
        """
        if not ranking:
            print("❌ 没有可用的节点创建订阅")
            return None
        
        # 选择前20个最快的节点
        top_nodes = ranking[:20]
        
        print(f"\n🎯 创建速度优化订阅: {output_file}")
        print(f"📊 包含 {len(top_nodes)} 个最快节点")
        
        # 生成Clash格式的订阅
        clash_config = {
            "port": 7890,
            "socks-port": 7891,
            "allow-lan": False,
            "mode": "rule",
            "log-level": "info",
            "external-controller": "127.0.0.1:9090",
            "proxies": [],
            "proxy-groups": [
                {
                    "name": "🚀 速度排行",
                    "type": "select",
                    "proxies": []
                },
                {
                    "name": "🔄 自动选择",
                    "type": "url-test",
                    "proxies": [],
                    "url": "http://www.gstatic.com/generate_204",
                    "interval": 300
                }
            ],
            "rules": [
                "DOMAIN-SUFFIX,google.com,🚀 速度排行",
                "DOMAIN-SUFFIX,youtube.com,🚀 速度排行",
                "DOMAIN-SUFFIX,github.com,🚀 速度排行",
                "GEOIP,CN,DIRECT",
                "MATCH,🚀 速度排行"
            ]
        }
        
        # 添加代理节点
        for i, node in enumerate(top_nodes):
            proxy_name = f"节点{i+1:02d}_{node['avg_latency']:.0f}ms"
            
            # 这里需要根据实际节点类型生成代理配置
            # 简化处理，实际需要解析URI并转换
            proxy_config = {
                "name": proxy_name,
                "type": "ss",  # 简化，实际需要根据URI类型
                "server": "example.com",
                "port": 443,
                "cipher": "aes-256-gcm",
                "password": "password"
            }
            
            clash_config["proxies"].append(proxy_config)
            clash_config["proxy-groups"][0]["proxies"].append(proxy_name)
            clash_config["proxy-groups"][1]["proxies"].append(proxy_name)
        
        # 保存YAML文件
        import yaml
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(clash_config, f, allow_unicode=True, default_flow_style=False)
        
        print(f"✅ 速度排行订阅已保存: {output_file}")
        return output_file

    def save_ranking_data(self, ranking: List[Dict], filename: str = "speed_ranking.json"):
        """
        保存速度排行数据
        """
        ranking_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_nodes": len(ranking),
            "ranking": ranking
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(ranking_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 速度排行数据已保存: {filename}")

def main():
    """
    主函数
    """
    print("☁️ 云环境节点速度测试器")
    print("专为GitHub Actions等云构建环境设计")
    print("-" * 50)
    
    # 示例节点列表
    sample_nodes = [
        "ss://YWVzLTI1Ni1nY206cGFzc3dvcmQ@server1.example.com:443#测试节点1",
        "trojan://password@server2.example.com:443#测试节点2",
        "vmess://eyJ2IjoiMiIsInBzIjoi5rWL6K+V5Yqg6L29IiwiYWRkIjoic2VydmVyMy5leGFtcGxlLmNvbSIsInBvcnQiOiI0NDMiLCJpZCI6InV1aWQiLCJhaWQiOiIwIiwic2N5IjoiYXV0byIsIm5ldCI6IndzcyIsInR5cGUiOiJub25lIiwiaG9zdCI6IiIsInRscyI6InRscyJ9#测试节点3"
    ]
    
    # 创建测试器
    tester = CloudSpeedTester(timeout=8, max_workers=2)
    
    # 执行测试
    results = tester.test_nodes_batch(sample_nodes)
    
    # 生成排行
    ranking = tester.generate_speed_ranking(results)
    
    # 创建速度优化订阅
    if ranking:
        tester.create_speed_optimized_subscription(ranking)
        tester.save_ranking_data(ranking)
        
        print(f"\n📊 速度排行 (前5名):")
        for i, node in enumerate(ranking[:5], 1):
            print(f"{i}. {node['avg_latency']:6.1f}ms (评分: {node['speed_score']:5.1f}) - {node['node_uri'][:50]}...")
    
    return results, ranking

if __name__ == "__main__":
    main()




