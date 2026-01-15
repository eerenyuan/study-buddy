"""
AI 服务 - 统一的 AI 功能入口

职责：
1. 管理所有 AI 分析器
2. 共享配置和客户端
3. 提供统一的入口
"""
from typing import Optional

from src.common import Logger
from .ai_config import AIConfig
from .vision_analyzer import VisionAnalyzer


class AIService:
    """AI 服务（统一入口）

    职责：
    1. 管理所有 AI 分析器
    2. 共享配置（API Key、Base URL）
    3. 提供统一的功能入口

    设计原则：
    - 统一管理：所有 AI 功能通过这个服务访问
    - 配置共享：所有分析器共享同一份配置
    - 易于扩展：添加新功能只需添加新方法
    """

    def __init__(self, config: AIConfig):
        """
        Args:
            config: AI 配置对象
        """
        self.config = config
        self.logger = Logger(config.log_dir)

        # Vision 分析器（延迟初始化）
        self._vision_analyzer: Optional[VisionAnalyzer] = None

        self.logger.log("ai", "info", f"AIService 初始化 - provider: kimi, model: {config.model}")

    def vision(self) -> VisionAnalyzer:
        """获取 Vision 分析器

        Returns:
            VisionAnalyzer 实例
        """
        if self._vision_analyzer is None:
            self._vision_analyzer = VisionAnalyzer(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                model=self.config.vision_model,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
                log_dir=self.config.log_dir
            )

        return self._vision_analyzer

    # ==================== 未来扩展 ====================

    # def chat(self) -> ChatAnalyzer:
    #     """获取聊天分析器（未来）"""
    #     pass

    # def solve(self) -> Solver:
    #     """获取解题器（未来）"""
    #     pass

    def get_status(self) -> dict:
        """获取服务状态

        Returns:
            状态字典
        """
        return {
            "provider": "kimi",
            "model": self.config.model,
            "vision_model": self.config.vision_model,
            "vision_available": self._vision_analyzer is not None
        }


# ==================== 工厂函数 ====================

_service_instance: Optional[AIService] = None
import threading


def create_ai_service(config: AIConfig) -> AIService:
    """创建 AI 服务

    Args:
        config: AI 配置对象

    Returns:
        AIService 实例
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = AIService(config)
    return _service_instance
