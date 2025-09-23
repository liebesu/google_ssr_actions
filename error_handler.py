#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
错误处理和重试机制
"""

import time
import logging
import functools
from typing import Callable, Any, Optional, Dict, List
import requests


class RetryConfig:
    """重试配置"""
    
    def __init__(self, 
                 max_retries: int = 3,
                 initial_delay: float = 1.0,
                 backoff_factor: float = 2.0,
                 max_delay: float = 60.0,
                 retryable_exceptions: Optional[List[type]] = None,
                 retryable_status_codes: Optional[List[int]] = None):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
        self.retryable_exceptions = retryable_exceptions or [
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.ChunkedEncodingError
        ]
        self.retryable_status_codes = retryable_status_codes or [429, 500, 502, 503, 504]


def retry_with_backoff(config: RetryConfig = None):
    """重试装饰器"""
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = logging.getLogger(func.__module__)
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    
                    # 检查HTTP状态码
                    if hasattr(result, 'status_code') and result.status_code in config.retryable_status_codes:
                        if attempt < config.max_retries:
                            delay = min(config.initial_delay * (config.backoff_factor ** attempt), config.max_delay)
                            logger.warning(f"HTTP {result.status_code} 错误，{delay}秒后重试 (尝试 {attempt + 1}/{config.max_retries + 1})")
                            time.sleep(delay)
                            continue
                    
                    return result
                    
                except tuple(config.retryable_exceptions) as e:
                    last_exception = e
                    if attempt < config.max_retries:
                        delay = min(config.initial_delay * (config.backoff_factor ** attempt), config.max_delay)
                        logger.warning(f"请求失败: {e}，{delay}秒后重试 (尝试 {attempt + 1}/{config.max_retries + 1})")
                        time.sleep(delay)
                    else:
                        logger.error(f"请求最终失败，已重试 {config.max_retries} 次: {e}")
                        raise e
                except Exception as e:
                    # 不可重试的异常直接抛出
                    logger.error(f"不可重试的异常: {e}")
                    raise e
            
            # 如果所有重试都失败了
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


class ErrorHandler:
    """统一错误处理"""
    
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger(__name__)
        self.error_stats = {
            'connection_errors': 0,
            'timeout_errors': 0,
            'http_errors': 0,
            'validation_errors': 0,
            'unknown_errors': 0
        }
    
    def handle_request_error(self, error: Exception, url: str = "") -> Dict[str, Any]:
        """处理请求错误"""
        error_info = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'url': url,
            'retryable': False,
            'suggested_action': 'skip'
        }
        
        if isinstance(error, requests.exceptions.Timeout):
            self.error_stats['timeout_errors'] += 1
            error_info.update({
                'retryable': True,
                'suggested_action': 'retry_with_longer_timeout'
            })
            self.logger.warning(f"请求超时: {url}")
            
        elif isinstance(error, requests.exceptions.ConnectionError):
            self.error_stats['connection_errors'] += 1
            error_info.update({
                'retryable': True,
                'suggested_action': 'retry_with_proxy_fallback'
            })
            self.logger.warning(f"连接错误: {url}")
            
        elif isinstance(error, requests.exceptions.HTTPError):
            self.error_stats['http_errors'] += 1
            status_code = getattr(error.response, 'status_code', 0) if hasattr(error, 'response') else 0
            
            if status_code in [429, 503]:  # Rate limiting
                error_info.update({
                    'retryable': True,
                    'suggested_action': 'retry_with_delay'
                })
            elif status_code in [403, 404]:  # Client errors
                error_info['suggested_action'] = 'skip_permanently'
                
            self.logger.warning(f"HTTP错误 {status_code}: {url}")
            
        else:
            self.error_stats['unknown_errors'] += 1
            self.logger.error(f"未知错误: {error} for {url}")
        
        return error_info
    
    def handle_validation_error(self, error: Exception, data: Any = None) -> Dict[str, Any]:
        """处理验证错误"""
        self.error_stats['validation_errors'] += 1
        
        error_info = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'data': str(data)[:100] if data else None,
            'suggested_action': 'log_and_continue'
        }
        
        self.logger.warning(f"数据验证错误: {error}")
        return error_info
    
    def get_error_summary(self) -> Dict[str, Any]:
        """获取错误统计摘要"""
        total_errors = sum(self.error_stats.values())
        
        return {
            'total_errors': total_errors,
            'error_breakdown': self.error_stats.copy(),
            'error_rate_by_type': {
                k: round(v / total_errors * 100, 2) if total_errors > 0 else 0
                for k, v in self.error_stats.items()
            }
        }
    
    def reset_stats(self):
        """重置错误统计"""
        for key in self.error_stats:
            self.error_stats[key] = 0


def safe_execute(func: Callable, *args, default_return=None, logger: logging.Logger = None, **kwargs) -> Any:
    """安全执行函数，捕获所有异常"""
    if logger is None:
        logger = logging.getLogger(__name__)
    
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"执行 {func.__name__} 失败: {e}")
        return default_return


# 常用的重试配置
NETWORK_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    initial_delay=1.0,
    backoff_factor=2.0,
    retryable_status_codes=[429, 500, 502, 503, 504, 408]
)

API_RETRY_CONFIG = RetryConfig(
    max_retries=2,
    initial_delay=2.0,
    backoff_factor=1.5,
    retryable_status_codes=[429, 503]
)

SUBSCRIPTION_RETRY_CONFIG = RetryConfig(
    max_retries=2,
    initial_delay=1.0,
    backoff_factor=2.0,
    retryable_status_codes=[403, 429, 500, 502, 503]  # 包含403因为订阅链接经常出现
)

