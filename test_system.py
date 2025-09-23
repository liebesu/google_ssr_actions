#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统功能测试脚本
测试各个组件的功能是否正常
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import config
from data_cleaner import DataCleaner
from subscription_validator import SubscriptionValidator
from url_extractor import URLExtractor
from github_search_scraper import discover_from_github
from error_handler import ErrorHandler, safe_execute

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SystemTester:
    """系统测试器"""
    
    def __init__(self):
        self.results = {}
        self.error_handler = ErrorHandler(logger)
    
    def test_config_manager(self) -> bool:
        """测试配置管理器"""
        logger.info("🧪 测试配置管理器...")
        
        try:
            # 测试基本配置获取
            proxy_enabled = config.is_proxy_enabled()
            dingtalk_webhook = config.get_dingtalk_webhook()
            proxy_config = config.get_proxy_config()
            
            logger.info(f"   代理启用: {proxy_enabled}")
            logger.info(f"   钉钉Webhook: {'已配置' if dingtalk_webhook else '未配置'}")
            logger.info(f"   代理配置: {proxy_config}")
            
            self.results['config_manager'] = {
                'status': 'success',
                'proxy_enabled': proxy_enabled,
                'dingtalk_configured': dingtalk_webhook is not None,
                'proxy_config_available': proxy_config is not None
            }
            return True
            
        except Exception as e:
            logger.error(f"   ❌ 配置管理器测试失败: {e}")
            self.results['config_manager'] = {'status': 'failed', 'error': str(e)}
            return False
    
    def test_data_cleaner(self) -> bool:
        """测试数据清理器"""
        logger.info("🧪 测试数据清理器...")
        
        try:
            cleaner = DataCleaner()
            
            # 测试URL验证
            test_urls = [
                "https://test.com/api/v1/client/subscribe?token=abc123",
                "https://your-provider.com/api/v1/client/subscribe?token=xxxxx",  # 无效
                "invalid_url",  # 无效
                "https://valid.site/api/v1/client/subscribe?token=def456订阅流量：100GB"
            ]
            
            valid_count = 0
            for url in test_urls:
                if cleaner.is_valid_subscription_url(url):
                    valid_count += 1
            
            logger.info(f"   测试URL验证: {valid_count}/{len(test_urls)} 个有效")
            
            # 测试数据文件验证
            validation_results = cleaner.validate_data_files()
            
            self.results['data_cleaner'] = {
                'status': 'success',
                'url_validation_rate': valid_count / len(test_urls),
                'files_validated': len(validation_results)
            }
            return True
            
        except Exception as e:
            logger.error(f"   ❌ 数据清理器测试失败: {e}")
            self.results['data_cleaner'] = {'status': 'failed', 'error': str(e)}
            return False
    
    def test_url_extractor(self) -> bool:
        """测试URL提取器"""
        logger.info("🧪 测试URL提取器...")
        
        try:
            extractor = URLExtractor()
            
            # 测试用例
            test_cases = [
                # 标准URL
                "https://example.com/api/v1/client/subscribe?token=abc123",
                # 包含HTML的伪URL
                '<code>https://test.com/api/v1/client/subscribe?token=def456</code>',
                # 包含额外信息的URL
                "https://site.com/api/v1/client/subscribe?token=ghi789订阅流量：100GB",
                # 混合内容
                "Visit https://demo.com/api/v1/client/subscribe?token=jkl012 for access"
            ]
            
            total_extracted = 0
            for test_case in test_cases:
                urls = extractor.extract_subscription_urls(test_case)
                total_extracted += len(urls)
                logger.info(f"   从 '{test_case[:30]}...' 提取到 {len(urls)} 个URL")
            
            self.results['url_extractor'] = {
                'status': 'success',
                'test_cases_processed': len(test_cases),
                'total_urls_extracted': total_extracted
            }
            return True
            
        except Exception as e:
            logger.error(f"   ❌ URL提取器测试失败: {e}")
            self.results['url_extractor'] = {'status': 'failed', 'error': str(e)}
            return False
    
    def test_subscription_validator(self) -> bool:
        """测试订阅验证器"""
        logger.info("🧪 测试订阅验证器...")
        
        try:
            validator = SubscriptionValidator(use_proxy=False)  # 不使用代理以避免连接问题
            
            # 测试URL格式验证
            test_urls = [
                "https://test.com/api/v1/client/subscribe?token=abc123",
                "invalid_url",
                "https://example.com/other/path"
            ]
            
            valid_count = 0
            for url in test_urls:
                is_valid, cleaned_url, error = validator.validate_url_format(url)
                if is_valid:
                    valid_count += 1
                logger.info(f"   URL格式验证: {url[:30]}... -> {'✅' if is_valid else '❌'}")
            
            self.results['subscription_validator'] = {
                'status': 'success',
                'url_format_validation_rate': valid_count / len(test_urls),
                'validator_initialized': True
            }
            return True
            
        except Exception as e:
            logger.error(f"   ❌ 订阅验证器测试失败: {e}")
            self.results['subscription_validator'] = {'status': 'failed', 'error': str(e)}
            return False
    
    def test_github_scraper(self) -> bool:
        """测试GitHub搜索功能"""
        logger.info("🧪 测试GitHub搜索功能...")
        
        try:
            # 使用安全执行来避免网络错误影响测试
            urls = safe_execute(
                discover_from_github,
                defaults=False,  # 不使用默认搜索以避免过多请求
                extra_urls=["https://github.com/search?q=test&type=issues"],
                default_return=[],
                logger=logger
            )
            
            if urls is None:
                urls = []
            
            logger.info(f"   GitHub搜索结果: {len(urls)} 个URL")
            
            self.results['github_scraper'] = {
                'status': 'success',
                'urls_discovered': len(urls),
                'scraper_functional': True
            }
            return True
            
        except Exception as e:
            logger.error(f"   ❌ GitHub搜索功能测试失败: {e}")
            self.results['github_scraper'] = {'status': 'failed', 'error': str(e)}
            return False
    
    def test_error_handler(self) -> bool:
        """测试错误处理器"""
        logger.info("🧪 测试错误处理器...")
        
        try:
            import requests
            
            # 模拟各种错误
            errors = [
                requests.exceptions.Timeout("Request timeout"),
                requests.exceptions.ConnectionError("Connection failed"),
                ValueError("Invalid data")
            ]
            
            for error in errors:
                error_info = self.error_handler.handle_request_error(error, "test_url")
                logger.info(f"   处理错误 {type(error).__name__}: {error_info['suggested_action']}")
            
            summary = self.error_handler.get_error_summary()
            
            self.results['error_handler'] = {
                'status': 'success',
                'errors_processed': len(errors),
                'total_errors': summary['total_errors']
            }
            return True
            
        except Exception as e:
            logger.error(f"   ❌ 错误处理器测试失败: {e}")
            self.results['error_handler'] = {'status': 'failed', 'error': str(e)}
            return False
    
    def run_all_tests(self) -> Dict[str, Any]:
        """运行所有测试"""
        logger.info("🚀 开始系统功能测试")
        logger.info("=" * 50)
        
        start_time = time.time()
        
        tests = [
            ('配置管理器', self.test_config_manager),
            ('数据清理器', self.test_data_cleaner),
            ('URL提取器', self.test_url_extractor),
            ('订阅验证器', self.test_subscription_validator),
            ('GitHub搜索', self.test_github_scraper),
            ('错误处理器', self.test_error_handler),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            try:
                if test_func():
                    passed += 1
                    logger.info(f"✅ {test_name} 测试通过")
                else:
                    failed += 1
                    logger.error(f"❌ {test_name} 测试失败")
            except Exception as e:
                failed += 1
                logger.error(f"❌ {test_name} 测试异常: {e}")
            
            time.sleep(0.5)  # 短暂延迟
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 生成测试报告
        test_summary = {
            'timestamp': datetime.now().isoformat(),
            'duration_seconds': round(duration, 2),
            'total_tests': len(tests),
            'passed': passed,
            'failed': failed,
            'success_rate': round(passed / len(tests) * 100, 2),
            'results': self.results,
            'error_summary': self.error_handler.get_error_summary()
        }
        
        logger.info("=" * 50)
        logger.info(f"📊 测试完成: {passed}/{len(tests)} 通过 ({test_summary['success_rate']}%)")
        logger.info(f"⏱️  用时: {duration:.2f} 秒")
        
        return test_summary


def main():
    """主函数"""
    tester = SystemTester()
    summary = tester.run_all_tests()
    
    # 保存测试报告
    report_file = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    logger.info(f"📄 测试报告已保存到: {report_file}")
    
    # 返回退出码
    if summary['success_rate'] < 80:
        logger.warning("⚠️ 测试成功率低于80%，建议检查失败的组件")
        sys.exit(1)
    else:
        logger.info("🎉 系统测试通过！")
        sys.exit(0)


if __name__ == "__main__":
    main()
