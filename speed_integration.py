#!/usr/bin/env python3
"""
集成到现有系统的速度评测功能
"""

import os
import sys
import json
import time
from typing import Dict, List, Optional
from speed_tester import SpeedTester

def integrate_speed_testing():
    """
    将速度测试集成到现有的aggregator_cli.py中
    """
    
    # 读取现有的节点数据
    data_dir = "data"
    if not os.path.exists(data_dir):
        print("❌ 数据目录不存在，请先运行主程序")
        return
    
    # 读取已验证的节点
    verified_nodes_file = os.path.join(data_dir, "verified_nodes.json")
    if not os.path.exists(verified_nodes_file):
        print("❌ 未找到已验证节点文件")
        return
    
    with open(verified_nodes_file, 'r', encoding='utf-8') as f:
        verified_nodes = json.load(f)
    
    print(f"📊 找到 {len(verified_nodes)} 个已验证节点")
    
    # 创建速度测试器
    tester = SpeedTester(timeout=15, max_workers=5)  # 降低并发避免被限制
    
    # 选择测试节点（前20个）
    test_nodes = verified_nodes[:20]
    print(f"🚀 开始测试前 {len(test_nodes)} 个节点...")
    
    # 执行速度测试
    start_time = time.time()
    results = tester.test_nodes_batch(test_nodes)
    end_time = time.time()
    
    print(f"⏱️ 测试完成，耗时: {end_time - start_time:.1f}秒")
    
    # 生成报告
    report = tester.generate_speed_report(results)
    
    # 保存结果
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    results_file = f"speed_test_results_{timestamp}.json"
    report_file = f"speed_test_report_{timestamp}.json"
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    # 打印结果
    print_speed_report(report)
    
    return results, report

def print_speed_report(report: Dict):
    """
    打印速度测试报告
    """
    print("\n" + "="*60)
    print("📊 节点速度测试报告")
    print("="*60)
    
    print(f"总节点数: {report['total_nodes']}")
    print(f"成功测试: {report['successful_nodes']}")
    print(f"成功率: {report['success_rate']:.1f}%")
    
    if report['avg_latency']:
        print(f"平均延迟: {report['avg_latency']:.1f}ms")
    
    if report['fastest_node']:
        fastest = report['fastest_node']
        print(f"最快节点: {fastest['avg_latency']:.1f}ms")
        print(f"  URI: {fastest['node_uri'][:50]}...")
    
    if report['slowest_node']:
        slowest = report['slowest_node']
        print(f"最慢节点: {slowest['avg_latency']:.1f}ms")
    
    print("\n🏆 速度排行榜 (前10名):")
    print("-" * 60)
    for i, node in enumerate(report['ranking'][:10], 1):
        uri_short = node['node_uri'][:40] + "..." if len(node['node_uri']) > 40 else node['node_uri']
        print(f"{i:2d}. {node['avg_latency']:6.1f}ms - {uri_short}")
    
    print("="*60)

def create_speed_optimized_subscription(results: List[Dict], output_file: str = "speed_optimized.yaml"):
    """
    基于速度测试结果创建优化的订阅文件
    """
    # 按速度排序
    successful_results = [r for r in results if r.get("success", False)]
    sorted_results = sorted(successful_results, key=lambda x: x.get("avg_latency", float('inf')))
    
    # 选择前10个最快的节点
    top_nodes = sorted_results[:10]
    
    print(f"\n🎯 创建速度优化订阅文件: {output_file}")
    print(f"包含 {len(top_nodes)} 个最快节点")
    
    # 这里可以集成到现有的YAML生成逻辑中
    # 暂时保存节点列表
    with open("speed_optimized_nodes.json", 'w', encoding='utf-8') as f:
        json.dump(top_nodes, f, ensure_ascii=False, indent=2)
    
    print("✅ 速度优化节点列表已保存")

def main():
    """
    主函数
    """
    print("🚀 节点速度评测工具")
    print("适用于国内江苏地区")
    print("-" * 40)
    
    try:
        results, report = integrate_speed_testing()
        
        # 创建速度优化的订阅
        create_speed_optimized_subscription(results)
        
        print("\n✅ 速度测试完成！")
        print("📁 结果文件:")
        print("  - speed_test_results_*.json (详细结果)")
        print("  - speed_test_report_*.json (测试报告)")
        print("  - speed_optimized_nodes.json (优化节点)")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())




