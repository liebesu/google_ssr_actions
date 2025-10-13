#!/usr/bin/env python3
"""
测试新的good.yaml格式
"""

import yaml

# 模拟good_nodes
good_nodes = [
    "ss://YWVzLTEyOC1nY206OTc2NjU1NDgtMjkwMi00NDlmLWE3OGMtNjJmNWQ0OGVmM2Qw@hk0b.rtuiwr.top:25308#%E5%AE%98%E7%BD%91-https%3A%2F%2Fggdd.fun",
    "ss://YWVzLTEyOC1nY206OTc2NjU1NDgtMjkwMi00NDlmLWE3OGMtNjJmNWQ0OGVmM2Qw@hk01b.rtuiwr.top:45641#%E9%A6%99%E6%B8%AF-01",
    "trojan://66ca69fd-bdea-4c15-917c-bd8dccc3facd@2c6f2139-838e-4478-9e47-55140df12640.hkglink.xyz:10101?allowInsecure=0&peer=sni.eos-suzhou-4.cmecloud.cn&sni=sni.eos-suzhou-4.cmecloud.cn#%F0%9F%87%AD%F0%9F%87%B0%20%E9%A6%99%E6%B8%AF%2001%20TR"
]

# 新的good_clash_yaml结构
good_clash_yaml = {
    "mixed-port": 7890,
    "allow-lan": False,
    "mode": "rule",
    "log-level": "info",
    "proxies": good_nodes,
    "proxy-groups": [
        {"name": "Node-Select", "type": "select", "proxies": good_nodes + ["Auto", "DIRECT"]},
        {"name": "Auto", "type": "url-test", "proxies": good_nodes, "url": "http://www.gstatic.com/generate_204", "interval": 300},
        {"name": "Media", "type": "select", "proxies": ["Node-Select", "Auto", "DIRECT"]},
        {"name": "Telegram", "type": "select", "proxies": ["Node-Select", "DIRECT"]},
        {"name": "Microsoft", "type": "select", "proxies": ["DIRECT", "Node-Select"]},
        {"name": "Apple", "type": "select", "proxies": ["DIRECT", "Node-Select"]},
        {"name": "Google", "type": "select", "proxies": ["Node-Select", "DIRECT"]},
        {"name": "GitHub", "type": "select", "proxies": ["Node-Select", "DIRECT"]},
        {"name": "Netflix", "type": "select", "proxies": ["Node-Select", "DIRECT"]},
        {"name": "YouTube", "type": "select", "proxies": ["Node-Select", "DIRECT"]},
        {"name": "Twitter", "type": "select", "proxies": ["Node-Select", "DIRECT"]},
        {"name": "Facebook", "type": "select", "proxies": ["Node-Select", "DIRECT"]},
        {"name": "Instagram", "type": "select", "proxies": ["Node-Select", "DIRECT"]},
        {"name": "Spotify", "type": "select", "proxies": ["Node-Select", "DIRECT"]},
        {"name": "Steam", "type": "select", "proxies": ["Node-Select", "DIRECT"]},
        {"name": "Final", "type": "select", "proxies": ["Node-Select", "Auto", "DIRECT"]}
    ],
    "rule-providers": {
        "ChinaIp": {
            "type": "http", "behavior": "classical",
            "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ChinaIp.list",
            "path": "./rules/ChinaIp.list", "interval": 86400
        }
    },
    "rules": [
        "DOMAIN-SUFFIX,local,DIRECT",
        "IP-CIDR,127.0.0.0/8,DIRECT",
        "IP-CIDR,172.16.0.0/12,DIRECT",
        "IP-CIDR,192.168.0.0/16,DIRECT",
        "IP-CIDR,10.0.0.0/8,DIRECT",
        "IP-CIDR,17.0.0.0/8,DIRECT",
        "IP-CIDR,100.64.0.0/10,DIRECT",
        "DOMAIN-SUFFIX,cn,DIRECT",
        "GEOIP,CN,DIRECT",
        "RULE-SET,ChinaIp,DIRECT",
        "MATCH,Final"
    ]
}

# 生成YAML
yaml_content = yaml.safe_dump(good_clash_yaml, allow_unicode=True, sort_keys=False, default_flow_style=False, indent=2, width=float('inf'))

print("=== 新的good.yaml格式 ===")
print(yaml_content[:500] + "..." if len(yaml_content) > 500 else yaml_content)

# 检查是否包含节点
print(f"\n=== 检查结果 ===")
print(f"是否包含proxies: {'proxies:' in yaml_content}")
print(f"是否包含proxy-providers: {'proxy-providers:' in yaml_content}")
print(f"节点数量: {len(good_nodes)}")
print(f"YAML行数: {yaml_content.count(chr(10))}")

