#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版SerpAPI密钥管理器
支持智能密钥选择、自动故障转移和最大化利用率

核心特性：
1. 智能密钥选择：按下次重置时间优先级选择密钥，最大化利用率
2. 自动故障转移：失败后自动切换到下一个时间窗口的密钥
3. 钉钉通知支持：配额状态监控和异常通知
4. 配额监控：实时检查所有密钥的配额状态

使用示例：
    # 基本使用
    mgr = EnhancedSerpAPIKeyManager('keys')
    optimal_key = mgr.get_optimal_key()
    
    # 支持故障转移的操作
    def search_operation(api_key):
        # 执行SerpAPI搜索操作
        return serpapi_search(api_key, query)
    
    result = mgr.try_key_with_fallback(search_operation)
"""

import requests
import json
import time
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

class EnhancedSerpAPIKeyManager:
    """增强版SerpAPI密钥管理器"""
    
    def __init__(self, keys_file: str = 'keys', dingtalk_webhook: str = None):
        """
        初始化密钥管理器
        
        Args:
            keys_file: 密钥文件路径
            dingtalk_webhook: 钉钉Webhook URL
        """
        self.keys_file = keys_file
        self.dingtalk_webhook = dingtalk_webhook
        self.logger = logging.getLogger(__name__)
        self.api_keys = self._load_api_keys()
        self.current_key_index = 0
        self.failed_keys = set()
        self.key_quotas = {}  # 存储密钥额度信息
        self.last_quota_check = None
        
    def _load_api_keys(self) -> List[str]:
        """从文件加载API密钥"""
        try:
            with open(self.keys_file, 'r', encoding='utf-8') as f:
                keys = [line.strip() for line in f if line.strip()]
            self.logger.info(f"加载了 {len(keys)} 个SerpAPI密钥")
            return keys
        except Exception as e:
            self.logger.error(f"加载密钥文件失败: {e}")
            return []
    
    def get_key_quota(self, api_key: str) -> Dict:
        """获取单个密钥的额度信息"""
        try:
            url = "https://serpapi.com/account"
            params = {'api_key': api_key}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'api_key': api_key,
                    'account_status': data.get('account_status', 'Unknown'),
                    'plan_name': data.get('plan_name', 'Unknown'),
                    'searches_per_month': data.get('searches_per_month', 0),
                    'total_searches_left': data.get('total_searches_left', 0),
                    'this_month_usage': data.get('this_month_usage', 0),
                    'this_hour_searches': data.get('this_hour_searches', 0),
                    'account_rate_limit_per_hour': data.get('account_rate_limit_per_hour', 0),
                    'response_time': response.elapsed.total_seconds()
                }
            else:
                return {
                    'success': False,
                    'api_key': api_key,
                    'error': f'HTTP {response.status_code}',
                    'response_time': response.elapsed.total_seconds()
                }
        except Exception as e:
            return {
                'success': False,
                'api_key': api_key,
                'error': str(e),
                'response_time': 0
            }
    
    def check_all_quotas(self, force_refresh: bool = False) -> List[Dict]:
        """
        检查所有密钥的额度信息
        
        Args:
            force_refresh: 是否强制刷新（忽略缓存）
            
        Returns:
            List[Dict]: 所有密钥的额度信息
        """
        # 如果距离上次检查不到5分钟且不强制刷新，则使用缓存
        if (not force_refresh and self.last_quota_check and 
            (datetime.now() - self.last_quota_check).seconds < 300):
            return list(self.key_quotas.values())
        
        self.logger.info("正在检查所有密钥的额度信息...")
        results = []
        
        for i, api_key in enumerate(self.api_keys, 1):
            self.logger.info(f"检查密钥 {i}/{len(self.api_keys)}: {api_key[:10]}...")
            
            result = self.get_key_quota(api_key)
            results.append(result)
            
            # 缓存成功的结果
            if result['success']:
                self.key_quotas[api_key] = result
            
            # 添加延迟避免请求过快
            if i < len(self.api_keys):
                time.sleep(1)
        
        self.last_quota_check = datetime.now()
        return results
    
    def get_optimal_key(self) -> Optional[str]:
        """
        获取最优密钥（按下次重置时间优先级选择，最大化利用率）
        
        策略：
        1. 优先选择下次重置时间最近的密钥（避免浪费即将重置的额度）
        2. 如果该密钥没有剩余额度，自动跳到下一个时间窗口的密钥
        3. 确保最大化密钥利用率
        
        Returns:
            str: 最优密钥
        """
        # 检查所有密钥额度
        quotas = self.check_all_quotas()
        
        # 过滤出激活状态的密钥（包括额度为0的，因为我们需要知道重置时间）
        active_keys = [q for q in quotas if q['success'] and q['account_status'] == 'Active']
        
        if not active_keys:
            self.logger.error("没有激活状态的API密钥")
            return None
        
        # 为每个密钥添加重置时间信息
        keys_with_reset = []
        for i, key_info in enumerate(active_keys):
            reset_date = self._calculate_next_reset_date(key_info, i + 1)
            key_info['reset_date'] = reset_date
            key_info['reset_datetime'] = self._parse_reset_date(reset_date)
            keys_with_reset.append(key_info)
        
        # 按重置时间排序（最近的重置时间优先）
        keys_with_reset.sort(key=lambda x: x['reset_datetime'])
        
        # 寻找第一个有剩余额度的密钥
        for key_info in keys_with_reset:
            remaining = key_info.get('total_searches_left', 0)
            if remaining > 0:
                optimal_key = key_info['api_key']
                reset_date = key_info['reset_date']
                self.logger.info(f"选择最优密钥: {optimal_key[:10]}... (剩余: {remaining}次, 重置时间: {reset_date})")
                return optimal_key
        
        # 如果所有密钥都没有剩余额度，选择重置时间最近的
        if keys_with_reset:
            key_info = keys_with_reset[0]
            optimal_key = key_info['api_key']
            reset_date = key_info['reset_date']
            self.logger.warning(f"所有密钥额度耗尽，选择重置时间最近的: {optimal_key[:10]}... (重置时间: {reset_date})")
            return optimal_key
        
        self.logger.error("没有可用的API密钥")
        return None
    
    def _calculate_next_reset_date(self, quota_info: Dict, key_index: int) -> str:
        """
        计算SerpAPI账户的下次重置时间
        
        Args:
            quota_info: 配额信息字典
            key_index: 密钥索引
            
        Returns:
            str: 下次重置时间字符串
        """
        try:
            from datetime import datetime, timedelta
            import calendar
            import json
            import os
            
            # 获取当前时间
            now = datetime.now()
            
            # 尝试从配置文件加载注册日期
            registration_dates_file = 'api_key_registration_dates.json'
            registration_dates = {}
            
            if os.path.exists(registration_dates_file):
                try:
                    with open(registration_dates_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        registration_dates = data.get('key_registration_dates', {})
                except Exception as e:
                    self.logger.warning(f"加载注册日期配置文件失败: {e}")
            
            # 获取当前API密钥
            current_api_key = quota_info.get('api_key', '')
            
            # 查找对应的注册日期
            registration_date_str = None
            for key, date in registration_dates.items():
                if key in current_api_key or current_api_key in key:
                    registration_date_str = date
                    break
            
            if registration_date_str:
                try:
                    # 解析注册日期
                    registration_date = datetime.strptime(registration_date_str, '%Y-%m-%d')
                    
                    # 计算下次重置时间（基于注册日期的每月对应日）
                    if now.month == 12:
                        next_reset = registration_date.replace(year=now.year + 1)
                    else:
                        next_reset = registration_date.replace(year=now.year, month=now.month + 1)
                    
                    # 如果计算出的重置时间已经过了，则使用下下个月
                    if next_reset <= now:
                        if now.month == 11:
                            next_reset = registration_date.replace(year=now.year + 1, month=1)
                        elif now.month == 12:
                            next_reset = registration_date.replace(year=now.year + 1, month=2)
                        else:
                            next_reset = registration_date.replace(year=now.year, month=now.month + 2)
                    
                    # 确保日期有效（处理2月29日等特殊情况）
                    last_day_of_month = calendar.monthrange(next_reset.year, next_reset.month)[1]
                    if next_reset.day > last_day_of_month:
                        next_reset = next_reset.replace(day=last_day_of_month)
                    
                    self.logger.debug(f"密钥 {key_index} 基于注册日期 {registration_date_str} 计算重置时间: {next_reset.strftime('%Y-%m-%d')}")
                    return next_reset.strftime("%Y-%m-%d")
                    
                except ValueError as e:
                    self.logger.warning(f"解析注册日期失败: {registration_date_str}, 错误: {e}")
            
            # 如果没有找到注册日期，使用默认逻辑（基于密钥索引）
            self.logger.debug(f"密钥 {key_index} 未找到注册日期，使用默认计算方式")
            
            # 使用密钥索引作为偏移量，确保不同密钥有不同的重置时间
            offset_days = (key_index - 1) * 7  # 每个密钥相差7天，避免过于接近
            
            # 计算下个月的同一天作为重置时间
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.replace(month=now.month + 1, day=1)
            
            # 添加偏移量
            reset_date = next_month + timedelta(days=offset_days)
            
            # 确保日期不超过下个月的最后一天
            last_day_of_month = calendar.monthrange(reset_date.year, reset_date.month)[1]
            if reset_date.day > last_day_of_month:
                reset_date = reset_date.replace(day=last_day_of_month)
            
            return reset_date.strftime("%Y-%m-%d")
            
        except Exception as e:
            self.logger.warning(f"计算重置时间失败: {e}")
            # 如果计算失败，返回下个月1号作为默认值
            from datetime import datetime
            now = datetime.now()
            if now.month == 12:
                return f"{now.year + 1}-01-01"
            else:
                return f"{now.year}-{now.month + 1:02d}-01"
    
    def _parse_reset_date(self, reset_date_str: str) -> datetime:
        """
        解析重置日期字符串为datetime对象，用于排序
        
        Args:
            reset_date_str: 重置日期字符串
            
        Returns:
            datetime: 解析后的日期对象
        """
        try:
            from datetime import datetime
            return datetime.strptime(reset_date_str, '%Y-%m-%d')
        except:
            # 如果解析失败，返回很远的未来时间，这样它会排在最后
            from datetime import datetime
            return datetime(2099, 12, 31)
    
    def get_available_key(self) -> Optional[str]:
        """
        获取可用的API密钥（兼容原接口）
        
        Returns:
            str: 可用的API密钥
        """
        # 优先使用最优密钥
        optimal_key = self.get_optimal_key()
        if optimal_key:
            return optimal_key
        
        # 如果最优密钥不可用，回退到轮换模式
        return self._get_next_available_key()
    
    def get_key_priority_list(self) -> List[str]:
        """
        获取按优先级排序的密钥列表（用于失败后自动切换）
        
        策略：
        1. 按下次重置时间排序（最近的优先）
        2. 有剩余额度的密钥排在前面
        3. 支持失败后自动切换到下一个密钥
        
        Returns:
            List[str]: 按优先级排序的密钥列表
        """
        # 检查所有密钥额度
        quotas = self.check_all_quotas()
        
        # 过滤出激活状态的密钥
        active_keys = [q for q in quotas if q['success'] and q['account_status'] == 'Active']
        
        if not active_keys:
            self.logger.error("没有激活状态的API密钥")
            return []
        
        # 为每个密钥添加重置时间信息
        keys_with_reset = []
        for i, key_info in enumerate(active_keys):
            reset_date = self._calculate_next_reset_date(key_info, i + 1)
            key_info['reset_date'] = reset_date
            key_info['reset_datetime'] = self._parse_reset_date(reset_date)
            keys_with_reset.append(key_info)
        
        # 按重置时间排序（最近的重置时间优先）
        keys_with_reset.sort(key=lambda x: x['reset_datetime'])
        
        # 分离有额度和无额度的密钥
        keys_with_quota = [k for k in keys_with_reset if k.get('total_searches_left', 0) > 0]
        keys_without_quota = [k for k in keys_with_reset if k.get('total_searches_left', 0) <= 0]
        
        # 优先返回有额度的密钥，然后是无额度的（按重置时间排序）
        priority_keys = keys_with_quota + keys_without_quota
        
        key_list = []
        for key_info in priority_keys:
            api_key = key_info['api_key']
            remaining = key_info.get('total_searches_left', 0)
            reset_date = key_info['reset_date']
            key_list.append(api_key)
            self.logger.debug(f"密钥优先级: {api_key[:10]}... (剩余: {remaining}次, 重置: {reset_date})")
        
        return key_list
    
    def try_key_with_fallback(self, operation_func, max_retries: int = None) -> Optional[Any]:
        """
        使用密钥执行操作，支持失败后自动切换到下一个密钥
        
        Args:
            operation_func: 操作函数，接收api_key参数
            max_retries: 最大重试次数，默认为密钥总数
            
        Returns:
            操作结果，如果所有密钥都失败则返回None
        """
        key_list = self.get_key_priority_list()
        
        if not key_list:
            self.logger.error("没有可用的密钥")
            return None
        
        if max_retries is None:
            max_retries = len(key_list)
        
        for i, api_key in enumerate(key_list[:max_retries]):
            try:
                self.logger.info(f"尝试使用密钥 {i+1}/{max_retries}: {api_key[:10]}...")
                result = operation_func(api_key)
                
                if result is not None:
                    self.logger.info(f"密钥 {api_key[:10]}... 操作成功")
                    return result
                else:
                    self.logger.warning(f"密钥 {api_key[:10]}... 操作失败，切换到下一个密钥")
                    
            except Exception as e:
                self.logger.warning(f"密钥 {api_key[:10]}... 操作异常: {str(e)}, 切换到下一个密钥")
                continue
        
        self.logger.error(f"所有 {max_retries} 个密钥都操作失败")
        return None
    
    def _get_next_available_key(self) -> Optional[str]:
        """轮换模式获取可用密钥"""
        if not self.api_keys:
            return None
        
        for i in range(len(self.api_keys)):
            key_index = (self.current_key_index + i) % len(self.api_keys)
            api_key = self.api_keys[key_index]
            
            if api_key not in self.failed_keys:
                self.current_key_index = key_index
                return api_key
        
        return None
    
    def send_quota_notification(self, quotas: List[Dict], round_completion: bool = False) -> bool:
        """
        发送额度信息到钉钉
        
        Args:
            quotas: 额度信息列表
            round_completion: 是否为轮次结束标识
            
        Returns:
            bool: 是否发送成功
        """
        if not self.dingtalk_webhook:
            self.logger.warning("未配置钉钉Webhook，跳过通知")
            return False
        
        try:
            # 过滤出可用的密钥
            available_keys = [q for q in quotas if q['success'] and q['account_status'] == 'Active']
            failed_keys = [q for q in quotas if not q['success'] or q['account_status'] != 'Active']
            
            # 计算汇总信息
            total_searches_left = sum(q['total_searches_left'] for q in available_keys)
            total_monthly_limit = sum(q['searches_per_month'] for q in available_keys)
            total_used = sum(q['this_month_usage'] for q in available_keys)
            overall_usage_rate = (total_used / total_monthly_limit * 100) if total_monthly_limit > 0 else 0
            
            # 构建钉钉消息
            from datetime import datetime
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 根据是否为轮次结束选择不同的标题和标识
            if round_completion:
                title = "🔚 此轮搜索结束 - SerpAPI密钥使用情况"
                round_identifier = "### 🎯 轮次状态\n**此轮搜索已结束**\n"
            else:
                title = "📊 SerpAPI密钥额度报告"
                round_identifier = ""
            
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": f"""## {title}

### ⏰ 检查时间
{current_time}

{round_identifier}### 📈 汇总信息
- **✅ 可用密钥**: {len(available_keys)}/{len(quotas)} (全部可用)
- **❌ 失效密钥**: {len(failed_keys)}/{len(quotas)} (无失效密钥)

### 💰 额度汇总
- **🎯 总剩余搜索次数**: {total_searches_left}次
- **📅 总月度限制**: {total_monthly_limit}次
- **📊 总已使用**: {total_used}次
- **📈 总体使用率**: {overall_usage_rate:.1f}%

### 🔑 各密钥使用情况
"""
                }
            }
            
            # 添加各密钥详情
            for i, quota in enumerate(available_keys, 1):
                usage_rate = (quota['this_month_usage'] / quota['searches_per_month']) * 100
                status_emoji = "⚠️" if usage_rate > 80 else "✅"
                status_text = "使用较多" if usage_rate > 50 else "几乎未使用" if usage_rate < 10 else "正常使用"
                
                message["markdown"]["text"] += f"- **密钥{i}**: {quota['total_searches_left']}/{quota['searches_per_month']} ({usage_rate:.1f}% 已用) - {status_text} {status_emoji}\n"
            
            # 添加失效密钥信息
            if failed_keys:
                message["markdown"]["text"] += f"\n### ❌ 失效密钥\n"
                for i, quota in enumerate(failed_keys, 1):
                    error_msg = quota.get('error', '未知错误')
                    message["markdown"]["text"] += f"- **密钥{i}**: {quota['api_key'][:10]}... - {error_msg}\n"
            
            # 添加建议
            if overall_usage_rate > 80:
                message["markdown"]["text"] += f"\n### ⚠️ 建议\n总体使用率较高({overall_usage_rate:.1f}%)，建议监控使用情况。\n"
            elif overall_usage_rate < 20:
                message["markdown"]["text"] += f"\n### ✅ 状态良好\n总体使用率较低({overall_usage_rate:.1f}%)，额度充足。\n"
            
            # 发送钉钉通知
            response = requests.post(
                self.dingtalk_webhook,
                json=message,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    self.logger.info("钉钉通知发送成功")
                    return True
                else:
                    self.logger.error(f"钉钉通知发送失败: {result.get('errmsg', '未知错误')}")
                    return False
            else:
                self.logger.error(f"钉钉通知发送失败: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"发送钉钉通知异常: {e}")
            return False
    
    def get_status(self) -> Dict:
        """获取密钥管理器状态"""
        return {
            'total_keys': len(self.api_keys),
            'failed_keys': len(self.failed_keys),
            'current_key_index': self.current_key_index,
            'current_key': self.api_keys[self.current_key_index][:10] + '...' if self.api_keys else None,
            'cached_quotas': len(self.key_quotas),
            'last_quota_check': self.last_quota_check.isoformat() if self.last_quota_check else None
        }
    
    def mark_key_failed(self, api_key: str):
        """标记密钥为失败"""
        self.failed_keys.add(api_key)
        self.logger.warning(f"标记密钥为失败: {api_key[:10]}...")
    
    def reset_failed_keys(self):
        """重置失败密钥记录"""
        self.failed_keys.clear()
        self.logger.info("已重置失败密钥记录")

def test_enhanced_key_manager():
    """测试增强版密钥管理器"""
    print("🧪 测试增强版SerpAPI密钥管理器")
    print("=" * 60)
    
    # 创建密钥管理器（不配置钉钉Webhook）
    key_manager = EnhancedSerpAPIKeyManager()
    
    # 检查所有密钥额度
    print("📊 检查所有密钥额度...")
    quotas = key_manager.check_all_quotas(force_refresh=True)
    
    # 显示结果
    print("\n📋 额度检查结果:")
    for i, quota in enumerate(quotas, 1):
        if quota['success']:
            usage_rate = (quota['this_month_usage'] / quota['searches_per_month']) * 100
            print(f"  密钥{i}: {quota['total_searches_left']}/{quota['searches_per_month']} "
                  f"({usage_rate:.1f}% 已用) - {quota['plan_name']}")
        else:
            print(f"  密钥{i}: 不可用 - {quota.get('error', '未知错误')}")
    
    # 测试最优密钥选择
    print(f"\n🎯 测试最优密钥选择:")
    optimal_key = key_manager.get_optimal_key()
    if optimal_key:
        print(f"  选择的最优密钥: {optimal_key[:10]}...")
    else:
        print(f"  没有可用的密钥")
    
    # 显示状态
    status = key_manager.get_status()
    print(f"\n📈 密钥管理器状态:")
    print(f"  总密钥数: {status['total_keys']}")
    print(f"  失败密钥数: {status['failed_keys']}")
    print(f"  缓存的额度信息: {status['cached_quotas']}")
    print(f"  上次检查时间: {status['last_quota_check']}")

if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    test_enhanced_key_manager()
