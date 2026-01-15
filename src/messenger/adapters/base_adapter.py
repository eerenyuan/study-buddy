"""
消息适配器基类

定义统一的接口，所有平台适配器都需要实现
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Callable
from src.common import Logger

from ..models.message import Message, MessageType


class MessageAdapter(ABC):
    """消息适配器基类

    定义所有平台适配器的统一接口

    设计原则：
    1. 单一职责：只负责与平台交互
    2. 平台无关：通过统一接口调用
    3. 可扩展：易于添加新平台
    """

    def __init__(self, platform_name: str, log_dir: str = "logs"):
        """
        Args:
            platform_name: 平台名称（wechat/telegram）
            log_dir: 日志目录
        """
        self.platform_name = platform_name
        self.logger = Logger(log_dir)

    # ==================== 发送消息 ====================

    @abstractmethod
    def send_text(self, content: str, recipient_id: str) -> bool:
        """发送文本消息

        Args:
            content: 消息内容
            recipient_id: 接收者 ID

        Returns:
            是否发送成功
        """
        pass

    def send_markdown(self, content: str, recipient_id: str) -> bool:
        """发送 Markdown 消息（可选实现）

        Args:
            content: Markdown 内容
            recipient_id: 接收者 ID

        Returns:
            是否发送成功
        """
        # 默认实现：作为文本发送
        self.logger.log("messenger", "warning", f"{self.platform_name} 不支持 Markdown，作为文本发送")
        return self.send_text(content, recipient_id)

    def send_image(self, image_path: str, recipient_id: str) -> bool:
        """发送图片消息（可选实现）

        Args:
            image_path: 图片路径
            recipient_id: 接收者 ID

        Returns:
            是否发送成功
        """
        # 默认实现：不支持
        self.logger.log("messenger", "warning", f"{self.platform_name} 不支持发送图片")
        return False

    def send_file(self, file_path: str, recipient_id: str) -> bool:
        """发送文件消息（可选实现）

        Args:
            file_path: 文件路径
            recipient_id: 接收者 ID

        Returns:
            是否发送成功
        """
        # 默认实现：不支持
        self.logger.log("messenger", "warning", f"{self.platform_name} 不支持发送文件")
        return False

    def send_card(self, title: str, description: str, url: str, recipient_id: str) -> bool:
        """发送卡片消息（可选实现）

        Args:
            title: 标题
            description: 描述
            url: 跳转链接
            recipient_id: 接收者 ID

        Returns:
            是否发送成功
        """
        # 默认实现：作为文本发送
        content = f"{title}\n{description}\n{url}"
        return self.send_text(content, recipient_id)

    # ==================== 接收消息（双向沟通）====================

    def start_receiving(self, on_message: Callable[[Message], None]):
        """开始接收消息（后台线程）

        Args:
            on_message: 收到消息时的回调函数

        Returns:
            是否启动成功
        """
        # 默认实现：不支持接收
        self.logger.log("messenger", "warning", f"{self.platform_name} 不支持接收消息")
        return False

    def stop_receiving(self):
        """停止接收消息"""
        # 默认实现：什么都不做
        pass

    # ==================== 生命周期 ====================

    @abstractmethod
    def initialize(self) -> bool:
        """初始化适配器

        Returns:
            是否初始化成功
        """
        pass

    @abstractmethod
    def shutdown(self):
        """关闭适配器"""
        pass

    # ==================== 辅助方法 ====================

    def send_message(self, message: Message) -> bool:
        """发送消息（统一入口）

        职责：
        1. 根据 Message 类型分发到具体的发送方法
        2. 设置消息的平台标识

        Args:
            message: Message 对象

        Returns:
            是否发送成功
        """
        # 设置平台标识
        message.platform = self.platform_name

        # 根据消息类型分发
        if message.type == MessageType.TEXT:
            return self.send_text(message.content, message.recipient_id)
        elif message.type == MessageType.IMAGE:
            return self.send_image(message.file_path, message.recipient_id)
        elif message.type == MessageType.MARKDOWN:
            return self.send_markdown(message.content, message.recipient_id)
        elif message.type == MessageType.TEXT_CARD:
            title = message.extra.get("title", "")
            url = message.extra.get("url", "")
            return self.send_card(title, message.content, url, message.recipient_id)
        else:
            self.logger.log("messenger", "error", f"不支持的消息类型: {message.type}")
            return False
