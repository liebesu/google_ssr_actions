#!/usr/bin/env python3
"""
SerpAPI 密钥管理 API 服务
提供密钥的添加、验证、删除等功能
"""

import os
import json
import hashlib
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from typing import Dict, List, Optional

app = Flask(__name__)

# 配置文件路径
KEYS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'serpapi_keys.json')
REGISTRATION_DATES_FILE = os.path.join(os.path.dirname(__file__), '..', 'api_key_registration_dates.json')

def load_keys() -> List[Dict]:
    """加载密钥列表"""
    try:
        if os.path.exists(KEYS_FILE):
            with open(KEYS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"加载密钥文件失败: {e}")
    return []

def save_keys(keys: List[Dict]) -> bool:
    """保存密钥列表"""
    try:
        os.makedirs(os.path.dirname(KEYS_FILE), exist_ok=True)
        with open(KEYS_FILE, 'w', encoding='utf-8') as f:
            json.dump(keys, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存密钥文件失败: {e}")
        return False

def load_registration_dates() -> Dict[str, str]:
    """加载注册日期配置"""
    try:
        if os.path.exists(REGISTRATION_DATES_FILE):
            with open(REGISTRATION_DATES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('key_registration_dates', {})
    except Exception as e:
        print(f"加载注册日期文件失败: {e}")
    return {}

def save_registration_dates(dates: Dict[str, str]) -> bool:
    """保存注册日期配置"""
    try:
        os.makedirs(os.path.dirname(REGISTRATION_DATES_FILE), exist_ok=True)
        data = {"key_registration_dates": dates}
        with open(REGISTRATION_DATES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存注册日期文件失败: {e}")
        return False

def mask_key(key: str) -> str:
    """掩码显示密钥"""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]

def validate_serpapi_key(key: str) -> Dict:
    """验证 SerpAPI 密钥"""
    try:
        # 使用 SerpAPI 的测试端点
        url = "https://serpapi.com/search"
        params = {
            "q": "test",
            "api_key": key,
            "engine": "google",
            "num": 1
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'error' in data:
                return {
                    "valid": False,
                    "error": data.get('error', '未知错误'),
                    "status": "invalid"
                }
            else:
                # 获取配额信息
                quota_info = {}
                if 'search_metadata' in data:
                    metadata = data['search_metadata']
                    quota_info = {
                        "used_searches": metadata.get('used_searches', 0),
                        "searches_per_month": metadata.get('searches_per_month', 0),
                        "total_searches_left": metadata.get('total_searches_left', 0),
                        "reset_date": metadata.get('reset_date', '')
                    }
                
                return {
                    "valid": True,
                    "quota_info": quota_info,
                    "status": "valid"
                }
        elif response.status_code == 401:
            return {
                "valid": False,
                "error": "API密钥无效或已过期",
                "status": "invalid"
            }
        elif response.status_code == 429:
            return {
                "valid": True,
                "error": "API配额已用完，但密钥有效",
                "status": "quota_exhausted"
            }
        else:
            return {
                "valid": False,
                "error": f"API请求失败 (状态码: {response.status_code})",
                "status": "error"
            }
            
    except requests.exceptions.Timeout:
        return {
            "valid": False,
            "error": "请求超时，请检查网络连接",
            "status": "error"
        }
    except requests.exceptions.RequestException as e:
        return {
            "valid": False,
            "error": f"网络错误: {str(e)}",
            "status": "error"
        }
    except Exception as e:
        return {
            "valid": False,
            "error": f"验证失败: {str(e)}",
            "status": "error"
        }

@app.route('/api/validate-key', methods=['POST'])
def validate_key():
    """验证密钥API"""
    try:
        data = request.get_json()
        if not data or 'key' not in data:
            return jsonify({"valid": False, "error": "缺少密钥参数"}), 400
        
        key = data['key'].strip()
        if not key:
            return jsonify({"valid": False, "error": "密钥不能为空"}), 400
        
        result = validate_serpapi_key(key)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"valid": False, "error": f"验证失败: {str(e)}"}), 500

@app.route('/api/add-key', methods=['POST'])
def add_key():
    """添加密钥API"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "缺少请求数据"}), 400
        
        required_fields = ['name', 'key', 'registration_date']
        for field in required_fields:
            if field not in data or not data[field].strip():
                return jsonify({"success": False, "error": f"缺少必需字段: {field}"}), 400
        
        # 检查密钥是否已存在
        keys = load_keys()
        key_hash = hashlib.sha256(data['key'].strip().encode()).hexdigest()
        
        for existing_key in keys:
            if existing_key.get('key_hash') == key_hash:
                return jsonify({"success": False, "error": "该密钥已存在"}), 400
        
        # 创建新密钥记录
        new_key = {
            "id": hashlib.md5(f"{data['name']}{data['key']}{datetime.now()}".encode()).hexdigest()[:12],
            "name": data['name'].strip(),
            "key_hash": key_hash,
            "key_masked": mask_key(data['key'].strip()),
            "registration_date": data['registration_date'],
            "description": data.get('description', '').strip(),
            "created_at": datetime.now().isoformat(),
            "last_validated": datetime.now().isoformat(),
            "status": data.get('validation_result', {}).get('status', 'pending'),
            "quota_info": data.get('validation_result', {}).get('quota_info', {}),
            "error": data.get('validation_result', {}).get('error', '')
        }
        
        # 添加到密钥列表
        keys.append(new_key)
        
        # 更新注册日期配置
        registration_dates = load_registration_dates()
        registration_dates[key_hash] = data['registration_date']
        
        # 保存数据
        if save_keys(keys) and save_registration_dates(registration_dates):
            return jsonify({"success": True, "key_id": new_key["id"]})
        else:
            return jsonify({"success": False, "error": "保存失败"}), 500
            
    except Exception as e:
        return jsonify({"success": False, "error": f"添加失败: {str(e)}"}), 500

@app.route('/api/keys', methods=['GET'])
def get_keys():
    """获取密钥列表API"""
    try:
        keys = load_keys()
        # 不返回完整的密钥哈希，只返回显示信息
        display_keys = []
        for key in keys:
            display_key = {
                "id": key["id"],
                "name": key["name"],
                "key_masked": key["key_masked"],
                "registration_date": key["registration_date"],
                "description": key["description"],
                "created_at": key["created_at"],
                "last_validated": key["last_validated"],
                "status": key["status"],
                "quota_info": key.get("quota_info", {}),
                "error": key.get("error", "")
            }
            display_keys.append(display_key)
        
        return jsonify(display_keys)
        
    except Exception as e:
        return jsonify({"error": f"获取密钥列表失败: {str(e)}"}), 500

@app.route('/api/revalidate-key/<key_id>', methods=['POST'])
def revalidate_key(key_id):
    """重新验证密钥API"""
    try:
        keys = load_keys()
        key_index = None
        
        for i, key in enumerate(keys):
            if key["id"] == key_id:
                key_index = i
                break
        
        if key_index is None:
            return jsonify({"success": False, "error": "密钥不存在"}), 404
        
        # 需要从其他地方获取完整密钥进行验证
        # 这里简化处理，实际应用中需要安全地存储和检索密钥
        return jsonify({"success": False, "error": "重新验证功能需要完整密钥，请重新添加"}), 400
        
    except Exception as e:
        return jsonify({"success": False, "error": f"验证失败: {str(e)}"}), 500

@app.route('/api/delete-key/<key_id>', methods=['DELETE'])
def delete_key(key_id):
    """删除密钥API"""
    try:
        keys = load_keys()
        key_to_delete = None
        
        for key in keys:
            if key["id"] == key_id:
                key_to_delete = key
                break
        
        if not key_to_delete:
            return jsonify({"success": False, "error": "密钥不存在"}), 404
        
        # 从列表中移除
        keys = [key for key in keys if key["id"] != key_id]
        
        # 从注册日期配置中移除
        registration_dates = load_registration_dates()
        if key_to_delete.get("key_hash") in registration_dates:
            del registration_dates[key_to_delete["key_hash"]]
        
        # 保存数据
        if save_keys(keys) and save_registration_dates(registration_dates):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "删除失败"}), 500
            
    except Exception as e:
        return jsonify({"success": False, "error": f"删除失败: {str(e)}"}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查API"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    # 创建必要的目录
    os.makedirs(os.path.dirname(KEYS_FILE), exist_ok=True)
    
    # 启动Flask应用
    app.run(host='0.0.0.0', port=5000, debug=True)


