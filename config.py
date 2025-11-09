"""
应用配置
"""

import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    """应用配置类"""

    # 飞书API配置
    FEISHU_APP_ID = os.getenv("FEISHU_APP_ID")
    FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")

    # DeepSeek API配置
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    # 工作流配置
    FORCE_REAL_FEISHU_DATA = os.getenv("FORCE_REAL_FEISHU_DATA", "false").lower() == "true"

    # 日志配置
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def has_feishu_auth(cls):
        """检查是否配置了飞书认证"""
        has_app_credentials = bool(cls.FEISHU_APP_ID and cls.FEISHU_APP_SECRET)
        return has_app_credentials

    @classmethod
    def should_use_real_feishu_api(cls):
        """判断是否应该使用真实的飞书API"""
        return cls.has_feishu_auth()

    @classmethod
    def allow_mock_fallback(cls):
        """判断是否允许Mock降级"""
        # 如果强制使用真实数据，则不允许降级
        return not cls.FORCE_REAL_FEISHU_DATA

# 全局配置实例
config = Config()