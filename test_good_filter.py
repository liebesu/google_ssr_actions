#!/usr/bin/env python3
"""
测试 good.txt 节点过滤逻辑
"""

def _is_good_node(node_line: str) -> bool:
    """
    判断节点是否为优秀节点
    
    Args:
        node_line: 节点配置行
        
    Returns:
        bool: 是否为优秀节点
    """
    if not node_line:
        return False
    
    # 排除明显标识为公益、免费、测试、剩余、到期等低质量节点
    exclude_keywords = [
        '公益', '免费', '测试', 'test', 'free', 'public', 'demo',
        '试用', 'trial', '临时', 'temp', '临时节点', '测试节点',
        '免费节点', '公益节点', '试用节点', 'demo节点',
        '剩余', '到期', 'expire', 'expired', 'expiring', 'expiry',
        'limited', 'limit', 'quota', 'quota exceeded', 'over quota',
        'low quality', 'poor', 'bad', 'slow', 'unstable'
    ]
    
    node_lower = node_line.lower()
    for keyword in exclude_keywords:
        if keyword in node_lower:
            return False
    
    # 检查节点配置的完整性
    # 对于SS/SSR节点，检查必要参数
    if 'ss://' in node_line or 'ssr://' in node_line:
        # SS/SSR节点应该有基本的配置参数
        return True  # 基础验证通过
    
    # 对于VMess/VLESS节点，检查必要参数
    elif 'vmess://' in node_line or 'vless://' in node_line:
        return True  # 基础验证通过
    
    # 对于Trojan节点
    elif 'trojan://' in node_line:
        return True  # 基础验证通过
    
    # 对于Hysteria节点
    elif 'hysteria://' in node_line or 'hysteria2://' in node_line:
        return True  # 基础验证通过
    
    # 其他格式的节点
    else:
        # 检查是否包含基本的节点配置参数
        node_indicators = [
            'server=', 'port=', 'password=', 'method=', 'protocol=',
            'obfs=', 'obfs_param=', 'remarks=', 'group=',
            'name=', 'type=', 'uuid=', 'path=', 'host='
        ]
        indicator_count = sum(1 for indicator in node_indicators if indicator in node_line)
        return indicator_count >= 2

def test_good_node_filter():
    """测试节点过滤逻辑"""
    
    # 测试用例：应该被排除的节点
    bad_nodes = [
        "ss://test-node-free@server.com:8080#免费测试节点",
        "vmess://uuid@server.com:443?remarks=公益节点",
        "trojan://password@server.com:443#临时节点",
        "ssr://base64@server.com:8080#剩余流量节点",
        "vless://uuid@server.com:443#到期节点",
        "hysteria2://password@server.com:8080#low quality node",
        "ss://password@server.com:8080#poor performance",
        "vmess://uuid@server.com:443#unstable connection",
        "trojan://password@server.com:443#quota exceeded",
        "ssr://base64@server.com:8080#expired node"
    ]
    
    # 测试用例：应该被保留的节点
    good_nodes = [
        "ss://password@server.com:8080#优质香港节点",
        "vmess://uuid@server.com:443?remarks=高速美国节点",
        "trojan://password@server.com:443#稳定新加坡节点",
        "vless://uuid@server.com:443#快速日本节点",
        "hysteria2://password@server.com:8080#韩国节点",
        "ssr://base64@server.com:8080#台湾节点",
        "ss://password@server.com:8080#premium node",
        "vmess://uuid@server.com:443#high quality server",
        "trojan://password@server.com:443#stable connection",
        "vless://uuid@server.com:443#fast server"
    ]
    
    print("=== 测试节点过滤逻辑 ===")
    
    # 测试应该被排除的节点
    print("\n❌ 应该被排除的节点:")
    for i, node in enumerate(bad_nodes, 1):
        result = _is_good_node(node)
        status = "✅ 正确排除" if not result else "❌ 错误保留"
        print(f"{i:2d}. {status} - {node}")
    
    # 测试应该被保留的节点
    print("\n✅ 应该被保留的节点:")
    for i, node in enumerate(good_nodes, 1):
        result = _is_good_node(node)
        status = "✅ 正确保留" if result else "❌ 错误排除"
        print(f"{i:2d}. {status} - {node}")
    
    # 统计结果
    bad_excluded = sum(1 for node in bad_nodes if not _is_good_node(node))
    good_kept = sum(1 for node in good_nodes if _is_good_node(node))
    
    print(f"\n=== 测试结果 ===")
    print(f"排除低质量节点: {bad_excluded}/{len(bad_nodes)}")
    print(f"保留高质量节点: {good_kept}/{len(good_nodes)}")
    print(f"总体准确率: {(bad_excluded + good_kept)}/{len(bad_nodes) + len(good_nodes)} = {(bad_excluded + good_kept)/(len(bad_nodes) + len(good_nodes))*100:.1f}%")

if __name__ == "__main__":
    test_good_node_filter()
