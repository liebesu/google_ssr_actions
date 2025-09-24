#!/usr/bin/env python3
"""测试SerpAPI密钥重置时间计算"""

import json
import hashlib
from datetime import datetime, timedelta
import calendar

def load_registration_dates():
    """加载密钥注册日期"""
    try:
        with open('api_key_registration_dates.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('key_registration_dates', {})
    except Exception as e:
        print(f"加载注册日期失败: {e}")
        return {}

def calculate_next_reset_date(registration_date_str):
    """计算下次重置时间"""
    try:
        now = datetime.now()
        registration_date = datetime.strptime(registration_date_str, '%Y-%m-%d')
        
        # 计算这个月的重置日期
        try:
            current_month = now.replace(day=registration_date.day)
        except ValueError:
            # 处理特殊情况（如2月30日）
            last_day = calendar.monthrange(now.year, now.month)[1]
            current_month = now.replace(day=min(registration_date.day, last_day))
        
        # 如果这个月的重置日期还没到，就用这个月的
        if current_month > now:
            next_reset = current_month
        else:
            # 否则使用下个月的重置日期
            if now.month == 12:
                next_reset = registration_date.replace(year=now.year + 1, month=1)
            else:
                try:
                    next_reset = registration_date.replace(year=now.year, month=now.month + 1)
                except ValueError:
                    # 处理特殊情况
                    next_month = now.month + 1
                    next_year = now.year
                    if next_month > 12:
                        next_month = 1
                        next_year += 1
                    last_day = calendar.monthrange(next_year, next_month)[1]
                    next_reset = datetime(next_year, next_month, min(registration_date.day, last_day))
        
        # 确保日期有效
        last_day_of_month = calendar.monthrange(next_reset.year, next_reset.month)[1]
        if next_reset.day > last_day_of_month:
            next_reset = next_reset.replace(day=last_day_of_month)
        
        return next_reset.strftime("%Y-%m-%d")
        
    except Exception as e:
        print(f"计算重置时间失败: {e}")
        return None

def main():
    print("🔍 SerpAPI密钥重置时间测试")
    print("=" * 50)
    
    # 加载注册日期
    registration_dates = load_registration_dates()
    print(f"📅 已加载 {len(registration_dates)} 个密钥的注册日期")
    
    # 当前时间
    now = datetime.now()
    print(f"⏰ 当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 为每个密钥计算重置时间
    for i, (key_hash, reg_date) in enumerate(registration_dates.items(), 1):
        print(f"🔑 密钥 {i}:")
        print(f"  哈希: {key_hash[:20]}...")
        print(f"  注册日期: {reg_date}")
        
        reset_date = calculate_next_reset_date(reg_date)
        if reset_date:
            print(f"  下次重置: {reset_date}")
            
            # 计算距离重置的天数
            reset_datetime = datetime.strptime(reset_date, '%Y-%m-%d')
            days_to_reset = (reset_datetime - now).days
            print(f"  距离重置: {days_to_reset} 天")
        else:
            print(f"  ❌ 计算失败")
        print()

if __name__ == "__main__":
    main()
