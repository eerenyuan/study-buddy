"""
消息适配器层

定义统一的接口，支持多个平台
"""

from .base_adapter import MessageAdapter
from .wechat_adapter import WeChatAdapter
from .telegram_adapter import TelegramAdapter

__all__ = [
    'MessageAdapter',
    'WeChatAdapter',
    'TelegramAdapter',
]
