"""
消息数据模型

支持双向消息传递
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime


class MessageDirection(Enum):
    """消息方向"""
    OUTGOING = "outgoing"  # 发送
    INCOMING = "incoming"  # 接收


class MessageType(Enum):
    """消息类型"""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    MARKDOWN = "markdown"
    TEXT_CARD = "text_card"


class MessageLevel(Enum):
    """消息级别"""
    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"


@dataclass
class Message:
    """消息模型（支持双向）

    设计原则：
    1. 统一的消息格式，适用于不同平台
    2. 支持发送和接收
    3. 可扩展的字段（通过 extra）
    """

    # 基础信息
    direction: MessageDirection  # 消息方向
    type: MessageType           # 消息类型
    content: str               # 消息内容

    # 元数据
    level: Optional[MessageLevel] = None  # 消息级别（发送时使用）
    timestamp: datetime = field(default_factory=datetime.now)  # 时间戳
    platform: Optional[str] = None        # 平台标识（wechat/telegram）

    # 接收相关信息（INCOMING 时使用）
    sender_id: Optional[str] = None       # 发送者 ID
    sender_name: Optional[str] = None     # 发送者名称
    chat_id: Optional[str] = None         # 会话 ID

    # 发送相关信息（OUTGOING 时使用）
    recipient_id: Optional[str] = None    # 接收者 ID
    sent: bool = False                    # 是否已发送
    sent_at: Optional[datetime] = None     # 发送时间

    # 附件信息（用于 IMAGE/FILE 类型）
    file_path: Optional[str] = None       # 文件路径（发送时）
    file_url: Optional[str] = None        # 文件 URL（接收时）
    media_id: Optional[str] = None        # 媒体 ID（企业微信上传后）

    # 扩展字段（用于平台特定信息）
    extra: Dict[str, Any] = field(default_factory=dict)

    # 回调信息（用于处理接收的消息）
    processed: bool = False              # 是否已处理
    callback_data: Optional[Dict[str, Any]] = None  # 回调数据

    def __repr__(self) -> str:
        direction_str = "→" if self.direction == MessageDirection.OUTGOING else "←"
        return f"Message({direction_str} {self.platform} {self.type.value}: {self.content[:30]}...)"

    # ==================== 工厂方法（用于创建发送消息）====================

    @classmethod
    def send_text(cls,
                  content: str,
                  recipient_id: str,
                  level: MessageLevel = MessageLevel.INFO,
                  platform: Optional[str] = None) -> "Message":
        """创建发送文本消息

        Args:
            content: 文本内容
            recipient_id: 接收者 ID
            level: 消息级别
            platform: 平台标识

        Returns:
            Message 对象
        """
        return cls(
            direction=MessageDirection.OUTGOING,
            type=MessageType.TEXT,
            content=content,
            level=level,
            platform=platform,
            recipient_id=recipient_id
        )

    @classmethod
    def send_markdown(cls,
                      content: str,
                      recipient_id: str,
                      level: MessageLevel = MessageLevel.INFO,
                      platform: Optional[str] = None) -> "Message":
        """创建发送 Markdown 消息

        Args:
            content: Markdown 内容
            recipient_id: 接收者 ID
            level: 消息级别
            platform: 平台标识

        Returns:
            Message 对象
        """
        return cls(
            direction=MessageDirection.OUTGOING,
            type=MessageType.MARKDOWN,
            content=content,
            level=level,
            platform=platform,
            recipient_id=recipient_id
        )

    @classmethod
    def send_image(cls,
                   image_path: str,
                   recipient_id: str,
                   level: MessageLevel = MessageLevel.INFO,
                   platform: Optional[str] = None) -> "Message":
        """创建发送图片消息

        Args:
            image_path: 图片路径
            recipient_id: 接收者 ID
            level: 消息级别
            platform: 平台标识

        Returns:
            Message 对象
        """
        return cls(
            direction=MessageDirection.OUTGOING,
            type=MessageType.IMAGE,
            content=f"[图片] {image_path}",
            level=level,
            platform=platform,
            recipient_id=recipient_id,
            file_path=image_path
        )

    @classmethod
    def send_card(cls,
                  content: str,
                  recipient_id: str,
                  title: Optional[str] = None,
                  url: Optional[str] = None,
                  level: MessageLevel = MessageLevel.INFO,
                  platform: Optional[str] = None) -> "Message":
        """创建发送卡片消息

        Args:
            content: 卡片内容
            recipient_id: 接收者 ID
            title: 卡片标题
            url: 卡片链接
            level: 消息级别
            platform: 平台标识

        Returns:
            Message 对象
        """
        return cls(
            direction=MessageDirection.OUTGOING,
            type=MessageType.TEXT_CARD,
            content=content,
            level=level,
            platform=platform,
            recipient_id=recipient_id,
            extra={
                "title": title,
                "url": url
            } if title or url else {}
        )
