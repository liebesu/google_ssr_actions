#!/usr/bin/env python3
"""
测试修复后的 good.txt 节点过滤逻辑
"""

import urllib.parse

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
    
    # 先尝试URL解码，然后转换为小写进行匹配
    try:
        decoded_line = urllib.parse.unquote(node_line)
        node_lower = decoded_line.lower()
    except:
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

def test_url_encoded_filtering():
    """测试URL编码的节点过滤"""
    
    # 从实际good.txt中提取的问题节点
    problematic_nodes = [
        "trojan://66ca69fd-bdea-4c15-917c-bd8dccc3facd@2c6f2139-838e-4478-9e47-55140df12640.hkglink.xyz:10101?allowInsecure=0&peer=sni.eos-suzhou-4.cmecloud.cn&sni=sni.eos-suzhou-4.cmecloud.cn#%E5%89%A9%E4%BD%99%E6%B5%81%E9%87%8F%EF%BC%9A153.65%20GB",
        "trojan://66ca69fd-bdea-4c15-917c-bd8dccc3facd@2c6f2139-838e-4478-9e47-55140df12640.hkglink.xyz:10101?allowInsecure=0&peer=sni.eos-suzhou-4.cmecloud.cn&sni=sni.eos-suzhou-4.cmecloud.cn#%E8%B7%9D%E7%A6%BB%E4%B8%8B%E6%AC%A1%E9%87%8D%E7%BD%AE%E5%89%A9%E4%BD%99%EF%BC%9A24%20%E5%A4%A9",
        "trojan://66ca69fd-bdea-4c15-917c-bd8dccc3facd@2c6f2139-838e-4478-9e47-55140df12640.hkglink.xyz:10101?allowInsecure=0&peer=sni.eos-suzhou-4.cmecloud.cn&sni=sni.eos-suzhou-4.cmecloud.cn#%E5%A5%97%E9%A4%90%E5%88%B0%E6%9C%9F%EF%BC%9A2026-04-02"
    ]
    
    # 正常的高质量节点
    good_nodes = [
        "hysteria2://e0fafa17-7ac1-4435-af1a-d61e2904f367@133.18.163.202:50000/?insecure=1&sni=www.microsoft.com&mport=50000-55000#%E6%97%A5%E6%9C%AC",
        "trojan://66ca69fd-bdea-4c15-917c-bd8dccc3facd@2c6f2139-838e-4478-9e47-55140df12640.hkglink.xyz:10101?allowInsecure=0&peer=sni.eos-suzhou-4.cmecloud.cn&sni=sni.eos-suzhou-4.cmecloud.cn#%F0%9F%87%AD%F0%9F%87%B0%20%E9%A6%99%E6%B8%AF%2001%20TR"
    ]
    
    print("=== 测试URL编码节点过滤 ===")
    
    # 测试问题节点（应该被排除）
    print("\n❌ 应该被排除的URL编码节点:")
    for i, node in enumerate(problematic_nodes, 1):
        result = _is_good_node(node)
        decoded_name = urllib.parse.unquote(node.split('#')[-1])
        status = "✅ 正确排除" if not result else "❌ 错误保留"
        print(f"{i}. {status} - {decoded_name}")
    
    # 测试正常节点（应该被保留）
    print("\n✅ 应该被保留的URL编码节点:")
    for i, node in enumerate(good_nodes, 1):
        result = _is_good_node(node)
        decoded_name = urllib.parse.unquote(node.split('#')[-1])
        status = "✅ 正确保留" if result else "❌ 错误排除"
        print(f"{i}. {status} - {decoded_name}")
    
    # 统计结果
    bad_excluded = sum(1 for node in problematic_nodes if not _is_good_node(node))
    good_kept = sum(1 for node in good_nodes if _is_good_node(node))
    
    print(f"\n=== 测试结果 ===")
    print(f"排除问题节点: {bad_excluded}/{len(problematic_nodes)}")
    print(f"保留正常节点: {good_kept}/{len(good_nodes)}")
    print(f"总体准确率: {(bad_excluded + good_kept)}/{len(problematic_nodes) + len(good_nodes)} = {(bad_excluded + good_kept)/(len(problematic_nodes) + len(good_nodes))*100:.1f}%")

if __name__ == "__main__":
    test_url_encoded_filtering()
