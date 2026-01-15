"""
AI 服务配置类
"""
from dataclasses import dataclass


@dataclass
class AIConfig:
    """AI 服务配置对象

    统一管理所有 AI 功能的配置
    """
    # Kimi API 配置
    api_key: str  # Kimi API Key
    base_url: str = "https://api.moonshot.cn/v1"  # API 基础 URL
    model: str = "moonshot-v1-8k"  # 默认模型

    # Vision 配置
    vision_model: str = "moonshot-vision"  # Vision 专用模型

    # 超时配置
    timeout: int = 30  # API 请求超时（秒）

    # 日志配置
    log_dir: str = "logs"

    # 高级配置
    max_retries: int = 3  # 最大重试次数
    retry_delay: int = 1  # 重试延迟（秒）
