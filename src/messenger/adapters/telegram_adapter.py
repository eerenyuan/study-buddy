"""
Telegram 消息适配器

支持发送文本、Markdown 消息和图片
"""
from typing import Optional

import httpx

from .base_adapter import MessageAdapter
from ..models.message import MessageType


class TelegramAdapter(MessageAdapter):
    """Telegram 适配器

    功能：
    1. 发送文本消息
    2. 发送 Markdown 消息
    3. 发送图片消息

    未来扩展：
    - 接收消息（通过 Webhook 或 Long Polling）
    - 交互按钮（Inline Keyboard）
    """

    def __init__(self,
                 bot_token: str,
                 log_dir: str = "logs"):
        """
        Args:
            bot_token: Bot Token
            log_dir: 日志目录
        """
        super().__init__("telegram", log_dir)
        self.bot_token = bot_token

    def initialize(self) -> bool:
        """初始化适配器"""
        if not self.bot_token:
            self.logger.log("messenger", "warning", "Telegram 未配置 bot_token，跳过初始化")
            return False

        self.logger.log("messenger", "info", "Telegram 初始化")

        # 测试连接
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            response = httpx.get(url, timeout=10)
            result = response.json()

            if result.get("ok"):
                bot_info = result.get("result", {})
                self.logger.log("messenger", "info",
                               f"Telegram Bot 连接成功: @{bot_info.get('username')}")
                return True
            else:
                error_desc = result.get("description", "未知错误")
                self.logger.log("messenger", "error", f"Telegram Bot 连接失败: {error_desc}")
                return False

        except Exception as e:
            self.logger.log("messenger", "error", f"Telegram Bot 连接异常: {e}")
            return False

    def shutdown(self):
        """关闭适配器"""
        self.logger.log("messenger", "info", "Telegram 适配器已关闭")

    # ==================== 发送消息 ====================

    def send_text(self, content: str, recipient_id: str) -> bool:
        """发送文本消息"""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        data = {
            "chat_id": recipient_id,
            "text": content
        }

        try:
            response = httpx.post(url, json=data, timeout=30)
            result = response.json()

            if result.get("ok"):
                self.logger.log("messenger", "info", f"Telegram 消息发送成功")
                return True
            else:
                error_desc = result.get("description", "未知错误")
                self.logger.log("messenger", "error", f"Telegram 消息发送失败: {error_desc}")
                return False

        except Exception as e:
            self.logger.log("messenger", "error", f"Telegram 消息发送异常: {e}")
            return False

    def send_markdown(self, content: str, recipient_id: str) -> bool:
        """发送 Markdown 消息"""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        data = {
            "chat_id": recipient_id,
            "text": content,
            "parse_mode": "Markdown"
        }

        try:
            response = httpx.post(url, json=data, timeout=30)
            result = response.json()

            if result.get("ok"):
                self.logger.log("messenger", "info", f"Telegram Markdown 消息发送成功")
                return True
            else:
                error_desc = result.get("description", "未知错误")
                self.logger.log("messenger", "error", f"Telegram Markdown 消息发送失败: {error_desc}")
                return False

        except Exception as e:
            self.logger.log("messenger", "error", f"Telegram Markdown 消息发送异常: {e}")
            return False

    def send_image(self, image_path: str, recipient_id: str) -> bool:
        """发送图片消息"""
        from pathlib import Path

        if not Path(image_path).exists():
            self.logger.log("messenger", "error", f"图片文件不存在: {image_path}")
            return False

        # 检查文件大小（Telegram 限制 10MB）
        file_size = Path(image_path).stat().st_size
        if file_size > 10 * 1024 * 1024:
            self.logger.log("messenger", "error", f"图片大小超过10MB限制: {file_size / 1024 / 1024:.2f}MB")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"

            with open(image_path, "rb") as f:
                files = {"photo": (Path(image_path).name, f)}
                data = {"chat_id": recipient_id}

                response = httpx.post(url, data=data, files=files, timeout=60)
                result = response.json()

            if result.get("ok"):
                self.logger.log("messenger", "info", f"Telegram 图片发送成功")
                return True
            else:
                error_desc = result.get("description", "未知错误")
                self.logger.log("messenger", "error", f"Telegram 图片发送失败: {error_desc}")
                return False

        except Exception as e:
            self.logger.log("messenger", "error", f"Telegram 图片发送异常: {e}")
            return False

    def send_card(self, title: str, description: str, url: str, recipient_id: str) -> bool:
        """发送卡片消息（作为 Markdown 发送）"""
        # Telegram 没有卡片类型，使用 Markdown 模拟
        content = f"*{title}*\n\n{description}\n\n[查看详情]({url})"
        return self.send_markdown(content, recipient_id)
