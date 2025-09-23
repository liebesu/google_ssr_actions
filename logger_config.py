#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
import glob

class DailyRotatingLogger:
    """按日期轮转的日志管理器，自动清理7天前的日志"""
    
    def __init__(self, name: str, log_dir: str = "logs", max_days: int = 7):
        """
        初始化日志管理器
        
        Args:
            name: 日志器名称
            log_dir: 日志目录
            max_days: 保留天数，默认7天
        """
        self.name = name
        self.log_dir = log_dir
        self.max_days = max_days
        
        # 创建日志目录
        os.makedirs(log_dir, exist_ok=True)
        
        # 设置日志器
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # 清除已有的处理器
        self.logger.handlers.clear()
        
        # 添加控制台处理器
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # 添加文件处理器（按日期轮转）
        log_file = os.path.join(log_dir, f"{name}.log")
        file_handler = TimedRotatingFileHandler(
            log_file,
            when='midnight',
            interval=1,
            backupCount=max_days,
            encoding='utf-8'
        )
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # 清理旧日志
        self.cleanup_old_logs()
    
    def cleanup_old_logs(self):
        """清理超过保留天数的日志文件"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.max_days)
            
            # 查找所有相关的日志文件
            log_pattern = os.path.join(self.log_dir, f"{self.name}.log*")
            log_files = glob.glob(log_pattern)
            
            deleted_count = 0
            for log_file in log_files:
                try:
                    # 获取文件修改时间
                    file_time = datetime.fromtimestamp(os.path.getmtime(log_file))
                    
                    # 如果文件超过保留天数，删除它
                    if file_time < cutoff_date:
                        os.remove(log_file)
                        deleted_count += 1
                        self.logger.info(f"删除过期日志文件: {log_file}")
                        
                except Exception as e:
                    self.logger.warning(f"删除日志文件失败 {log_file}: {e}")
            
            if deleted_count > 0:
                self.logger.info(f"清理完成，删除了 {deleted_count} 个过期日志文件")
            else:
                self.logger.debug("没有需要清理的过期日志文件")
                
        except Exception as e:
            self.logger.error(f"清理日志文件时出错: {e}")
    
    def get_logger(self):
        """获取配置好的日志器"""
        return self.logger
    
    def log_subscription_found(self, url: str, analysis_result: dict):
        """记录发现的订阅链接"""
        self.logger.info(f"发现可用订阅: {url}")
        
        if analysis_result.get('node_analysis'):
            analysis = analysis_result['node_analysis']
            node_count = analysis.get('total_nodes', 0)
            protocols = analysis.get('node_types', {})
            method = analysis.get('analysis_method', '未知')
            
            protocol_info = ", ".join([f"{p}({c})" for p, c in protocols.items() if c > 0])
            self.logger.info(f"  节点信息: {node_count}个节点, 协议: {protocol_info}, 分析方式: {method}")
        
        if analysis_result.get('traffic_info'):
            traffic = analysis_result['traffic_info']
            remaining = traffic.get('remaining_traffic', '未知')
            total = traffic.get('total_traffic', '未知')
            unit = traffic.get('traffic_unit', 'GB')
            
            self.logger.info(f"  流量信息: 剩余 {remaining} {unit}, 总量 {total} {unit}")
        
        self.logger.info(f"  状态码: {analysis_result.get('status_code', 'N/A')}")
    
    def log_dingtalk_sent(self, url: str, success: bool):
        """记录钉钉通知发送结果"""
        if success:
            self.logger.info(f"钉钉通知发送成功: {url}")
        else:
            self.logger.error(f"钉钉通知发送失败: {url}")
    
    def log_search_summary(self, time_range: str, found_count: int):
        """记录搜索摘要"""
        self.logger.info(f"搜索完成 [{time_range}]: 发现 {found_count} 个唯一URL")
    
    def log_daily_summary(self, total_found: int, total_notified: int):
        """记录每日摘要"""
        self.logger.info("=" * 60)
        self.logger.info("每日摘要统计")
        self.logger.info(f"总发现URL数量: {total_found}")
        self.logger.info(f"发送钉钉通知数量: {total_notified}")
        self.logger.info(f"通知成功率: {(total_notified/total_found*100):.1f}%" if total_found > 0 else "通知成功率: 0%")
        self.logger.info("=" * 60)

def get_logger(name: str) -> logging.Logger:
    """获取配置好的日志器的便捷函数"""
    daily_logger = DailyRotatingLogger(name)
    return daily_logger.get_logger()

def get_subscription_logger() -> DailyRotatingLogger:
    """获取订阅检查专用的日志器"""
    return DailyRotatingLogger("subscription_checker")

def get_scraper_logger() -> DailyRotatingLogger:
    """获取搜索器专用的日志器"""
    return DailyRotatingLogger("google_scraper")
