#!/usr/bin/env python3
"""
测试URI到Clash代理对象转换
"""

import yaml

def _uri_to_clash_proxy(uri: str) -> dict:
    """
    将URI格式的节点转换为Clash代理对象格式
    """
    try:
        import urllib.parse
        
        # 解析URI
        if '://' not in uri:
            return None
            
        scheme, rest = uri.split('://', 1)
        
        # 处理不同的协议
        if scheme == 'ss':
            # SS格式: ss://base64@server:port#name
            if '@' in rest:
                auth_part, server_part = rest.split('@', 1)
                if '#' in server_part:
                    server_port, name = server_part.split('#', 1)
                    name = urllib.parse.unquote(name)
                else:
                    server_port = server_part
                    name = "SS节点"
                
                if ':' in server_port:
                    server, port = server_port.split(':', 1)
                    port = int(port)
                else:
                    server = server_port
                    port = 443
                
                # 解码base64认证信息
                try:
                    import base64
                    auth_decoded = base64.b64decode(auth_part + '==').decode('utf-8')
                    method, password = auth_decoded.split(':', 1)
                except:
                    return None
                
                return {
                    "name": name,
                    "type": "ss",
                    "server": server,
                    "port": port,
                    "cipher": method,
                    "password": password
                }
        
        elif scheme == 'trojan':
            # Trojan格式: trojan://password@server:port?params#name
            if '@' in rest:
                password, rest = rest.split('@', 1)
                if '#' in rest:
                    server_part, name = rest.split('#', 1)
                    name = urllib.parse.unquote(name)
                else:
                    server_part = rest
                    name = "Trojan节点"
                
                if '?' in server_part:
                    server_port, params = server_part.split('?', 1)
                else:
                    server_port = server_part
                    params = ""
                
                if ':' in server_port:
                    server, port = server_port.split(':', 1)
                    port = int(port)
                else:
                    server = server_port
                    port = 443
                
                proxy = {
                    "name": name,
                    "type": "trojan",
                    "server": server,
                    "port": port,
                    "password": password
                }
                
                # 解析参数
                if params:
                    param_dict = urllib.parse.parse_qs(params)
                    if 'sni' in param_dict:
                        proxy["sni"] = param_dict['sni'][0]
                    if 'allowInsecure' in param_dict:
                        proxy["skip-cert-verify"] = param_dict['allowInsecure'][0] == '1'
                
                return proxy
        
        elif scheme == 'hysteria2':
            # Hysteria2格式: hysteria2://password@server:port?params#name
            if '@' in rest:
                password, rest = rest.split('@', 1)
                if '#' in rest:
                    server_part, name = rest.split('#', 1)
                    name = urllib.parse.unquote(name)
                else:
                    server_part = rest
                    name = "Hysteria2节点"
                
                if '?' in server_part:
                    server_port, params = server_part.split('?', 1)
                else:
                    server_port = server_part
                    params = ""
                
                if ':' in server_port:
                    server, port = server_port.split(':', 1)
                    # 处理端口号可能包含额外参数的情况
                    if '/' in port:
                        port = port.split('/')[0]
                    port = int(port)
                else:
                    server = server_port
                    port = 443
                
                proxy = {
                    "name": name,
                    "type": "hysteria2",
                    "server": server,
                    "port": port,
                    "password": password
                }
                
                # 解析参数
                if params:
                    param_dict = urllib.parse.parse_qs(params)
                    if param_dict.get('sni'):
                        proxy["sni"] = param_dict['sni'][0]
                    if param_dict.get('insecure') == ['1']:
                        proxy["skip-cert-verify"] = True
                
                return proxy
        
        return None
        
    except Exception as e:
        print(f"解析节点URI失败: {uri}, 错误: {e}")
        return None

# 测试节点
test_nodes = [
    "ss://YWVzLTEyOC1nY206OTc2NjU1NDgtMjkwMi00NDlmLWE3OGMtNjJmNWQ0OGVmM2Qw@hk0b.rtuiwr.top:25308#%E5%AE%98%E7%BD%91-https%3A%2F%2Fggdd.fun",
    "trojan://66ca69fd-bdea-4c15-917c-bd8dccc3facd@2c6f2139-838e-4478-9e47-55140df12640.hkglink.xyz:10101?allowInsecure=0&peer=sni.eos-suzhou-4.cmecloud.cn&sni=sni.eos-suzhou-4.cmecloud.cn#%F0%9F%87%AD%F0%9F%87%B0%20%E9%A6%99%E6%B8%AF%2001%20TR",
    "hysteria2://e0fafa17-7ac1-4435-af1a-d61e2904f367@133.18.163.202:50000/?insecure=1&sni=www.microsoft.com&mport=50000-55000#%E6%97%A5%E6%9C%AC"
]

print("=== 测试URI转换 ===")
clash_proxies = []
for uri in test_nodes:
    proxy_obj = _uri_to_clash_proxy(uri)
    if proxy_obj:
        clash_proxies.append(proxy_obj)
        print(f"转换成功: {proxy_obj['name']} ({proxy_obj['type']})")
    else:
        print(f"转换失败: {uri}")

print(f"\n=== 转换结果 ===")
print(f"成功转换: {len(clash_proxies)} 个节点")

# 生成测试YAML
test_yaml = {
    "mixed-port": 7890,
    "allow-lan": False,
    "mode": "rule",
    "log-level": "info",
    "proxies": clash_proxies,
    "proxy-groups": [
        {"name": "Node-Select", "type": "select", "proxies": [proxy["name"] for proxy in clash_proxies] + ["Auto", "DIRECT"]},
        {"name": "Auto", "type": "url-test", "proxies": [proxy["name"] for proxy in clash_proxies], "url": "http://www.gstatic.com/generate_204", "interval": 300},
    ],
    "rules": [
        "DOMAIN-SUFFIX,local,DIRECT",
        "MATCH,Final"
    ]
}

yaml_content = yaml.safe_dump(test_yaml, allow_unicode=True, sort_keys=False, default_flow_style=False, indent=2, width=float('inf'))
print(f"\n=== 生成的YAML ===")
print(yaml_content[:500] + "..." if len(yaml_content) > 500 else yaml_content)



