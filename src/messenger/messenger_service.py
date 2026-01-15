"""
Messenger 服务类

业务层：封装消息发送和接收的业务逻辑

架构：
┌─────────────────────────────────────┐
│     Web Layer (Flask Routes)        │  ← HTTP 请求处理
├─────────────────────────────────────┤
│     MessengerService (业务层)       │  ← 业务逻辑协调
│     - send()                        │
│     - broadcast()                   │
│     - on_message()                  │
├─────────────────────────────────────┤
│     AdapterConfig (配置层)          │  ← 显式依赖注入
│     - default_recipient             │
│     - on_receive_callback           │
├─────────────────────────────────────┤
│     MessageAdapter (适配器层)       │  ← 平台实现
│     - WeChatAdapter                │
│     - TelegramAdapter               │
└─────────────────────────────────────┘
"""
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any
from pathlib import Path

from src.common import Logger
from .adapters import MessageAdapter, WeChatAdapter, TelegramAdapter
from .models import Message, MessageType, MessageLevel


@dataclass
class MessengerConfig:
    """Messenger 服务配置对象

    使用 dataclass 封装所有配置项，类型安全且易于扩展
    """
    # 平台配置
    wechat_corpid: Optional[str] = None
    wechat_secret: Optional[str] = None
    wechat_agentid: Optional[str] = None
    wechat_recipient: Optional[str] = None

    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # 默认配置
    default_platform: str = "wechat"  # 默认平台
    default_recipient: Optional[str] = None  # 默认接收人

    # 接收消息配置（未来扩展）
    enable_receiving: bool = False  # 是否启用接收
    receive_callback: Optional[Callable[[Message], None]] = None  # 接收回调

    # 日志配置
    log_dir: str = "logs"

    # 项目根目录（用于解析相对路径）
    project_root: Optional[Path] = None


class MessengerService:
    """Messenger 服务类

    职责：
    1. 管理多个消息适配器
    2. 提供统一的发送接口
    3. 处理消息接收（未来扩展）
    4. 支持多平台广播

    设计原则：
    - 显式依赖注入（使用配置对象）
    - 单一职责（只管理消息传递）
    - 可扩展（易于添加新平台）
    - 支持双向沟通（架构已预留）
    """

    def __init__(self,
                 wechat_adapter: Optional[MessageAdapter] = None,
                 telegram_adapter: Optional[MessageAdapter] = None,
                 config: MessengerConfig = None):
        """
        Args:
            wechat_adapter: 企业微信适配器（可选）
            telegram_adapter: Telegram 适配器（可选）
            config: 服务配置对象
        """
        self.config = config or MessengerConfig()
        self.logger = Logger(self.config.log_dir)

        # 适配器列表
        self.adapters: List[MessageAdapter] = []

        # 添加适配器
        if wechat_adapter:
            self.adapters.append(wechat_adapter)
        if telegram_adapter:
            self.adapters.append(telegram_adapter)

        self.logger.log("messenger", "info",
                       f"MessengerService 初始化 - 已加载 {len(self.adapters)} 个适配器")

    @property
    def has_adapters(self) -> bool:
        """是否有可用的适配器"""
        return len(self.adapters) > 0

    # ==================== 发送消息（简单 API）====================

    def send(self,
             content: str,
             level: MessageLevel = MessageLevel.INFO,
             platform: Optional[str] = None) -> bool:
        """发送消息（简化版 API）

        Args:
            content: 消息内容
            level: 消息级别
            platform: 指定平台（None 表示使用所有平台）

        Returns:
            是否有任意一个发送成功
        """
        if platform:
            return self._send_to_platform_text(content, level, platform)
        else:
            return self._send_to_all_text(content, level)

    def send_image(self, image_path: str, level: MessageLevel = MessageLevel.INFO) -> bool:
        """发送图片（简化版 API）

        Args:
            image_path: 图片路径
            level: 消息级别

        Returns:
            是否有任意一个发送成功
        """
        return self._send_to_all_image(image_path, level)

    # ==================== 发送消息（完整 API）====================

    def send_message(self, message: Message, platform: Optional[str] = None) -> bool:
        """发送消息（完整 API）

        Args:
            message: Message 对象
            platform: 指定平台（None 表示使用所有平台）

        Returns:
            是否有任意一个发送成功
        """
        if platform:
            return self._send_to_platform_message(message, platform)
        else:
            return self._send_to_all_message(message)

    # ==================== 内部方法 ====================

    def _send_to_all_text(self, content: str, level: MessageLevel) -> bool:
        """发送文本到所有平台"""
        success = False
        for adapter in self.adapters:
            try:
                recipient = self._get_default_recipient(adapter.platform_name)
                message = Message.send_text(content, recipient, level)
                if adapter.send_message(message):
                    success = True
            except Exception as e:
                self.logger.log("messenger", "error", f"适配器异常: {e}")

        return success

    def _send_to_all_image(self, image_path: str, level: MessageLevel) -> bool:
        """发送图片到所有平台"""
        success = False
        for adapter in self.adapters:
            try:
                recipient = self._get_default_recipient(adapter.platform_name)
                message = Message.send_image(image_path, recipient, level)
                if adapter.send_message(message):
                    success = True
            except Exception as e:
                self.logger.log("messenger", "error", f"适配器异常: {e}")

        return success

    def _send_to_all_message(self, message: Message) -> bool:
        """发送 Message 到所有平台（克隆 Message 给每个平台）"""
        success = False
        for adapter in self.adapters:
            try:
                # 为每个平台设置 recipient_id
                msg_copy = message
                msg_copy.recipient_id = self._get_default_recipient(adapter.platform_name)
                if adapter.send_message(msg_copy):
                    success = True
            except Exception as e:
                self.logger.log("messenger", "error", f"适配器异常: {e}")

        return success

    def _send_to_platform_text(self, content: str, level: MessageLevel, platform: str) -> bool:
        """发送文本到指定平台"""
        for adapter in self.adapters:
            if adapter.platform_name == platform:
                recipient = self._get_default_recipient(platform)
                message = Message.send_text(content, recipient, level)
                return adapter.send_message(message)

        self.logger.log("messenger", "error", f"未找到平台适配器: {platform}")
        return False

    def _send_to_platform_message(self, message: Message, platform: str) -> bool:
        """发送 Message 到指定平台"""
        for adapter in self.adapters:
            if adapter.platform_name == platform:
                message.recipient_id = self._get_default_recipient(platform)
                return adapter.send_message(message)

        self.logger.log("messenger", "error", f"未找到平台适配器: {platform}")
        return False

    def _get_default_recipient(self, platform: str) -> str:
        """获取平台的默认接收人"""
        if platform == "wechat":
            return self.config.wechat_recipient or self.config.default_recipient or ""
        elif platform == "telegram":
            return self.config.telegram_chat_id or self.config.default_recipient or ""
        else:
            return self.config.default_recipient or ""

    # ==================== 接收消息（未来扩展）====================

    def start_receiving(self, on_message: Callable[[Message], None]):
        """开始接收消息（双向沟通）

        Args:
            on_message: 收到消息时的回调函数

        Returns:
            是否启动成功
        """
        if not self.config.enable_receiving:
            self.logger.log("messenger", "warning", "接收消息未启用")
            return False

        success = False
        for adapter in self.adapters:
            try:
                if adapter.start_receiving(on_message):
                    success = True
            except Exception as e:
                self.logger.log("messenger", "error", f"启动接收异常: {e}")

        return success

    def stop_receiving(self):
        """停止接收消息"""
        for adapter in self.adapters:
            try:
                adapter.stop_receiving()
            except Exception as e:
                self.logger.log("messenger", "error", f"停止接收异常: {e}")

    # ==================== 状态查询 ====================

    def get_status(self) -> Dict[str, Any]:
        """获取服务状态

        Returns:
            状态字典，包含：
            - has_adapters: 是否有可用适配器
            - adapter_count: 适配器数量
            - platforms: 可用平台列表
        """
        return {
            "has_adapters": self.has_adapters,
            "adapter_count": len(self.adapters),
            "platforms": [adapter.platform_name for adapter in self.adapters]
        }

    # ==================== 关闭 ====================

    def shutdown(self):
        """关闭服务"""
        for adapter in self.adapters:
            try:
                adapter.shutdown()
            except Exception as e:
                self.logger.log("messenger", "error", f"关闭适配器异常: {e}")

        self.logger.log("messenger", "info", "MessengerService 已关闭")


# ==================== 工厂函数 ====================

def create_messenger_service(config: MessengerConfig) -> MessengerService:
    """创建 Messenger 服务

    Args:
        config: 服务配置对象

    Returns:
        MessengerService 实例
    """
    adapters = []

    # 创建企业微信适配器
    if config.wechat_corpid and config.wechat_secret and config.wechat_recipient:
        wechat = WeChatAdapter(
            corpid=config.wechat_corpid,
            corpsecret=config.wechat_secret,
            agentid=config.wechat_agentid,
            log_dir=config.log_dir,
            project_root=config.project_root
        )
        if wechat.initialize():
            adapters.append(wechat)

    # 创建 Telegram 适配器
    if config.telegram_token and config.telegram_chat_id:
        telegram = TelegramAdapter(
            bot_token=config.telegram_token,
            log_dir=config.log_dir
        )
        if telegram.initialize():
            adapters.append(telegram)

    # 根据适配器创建服务
    if "wechat" in [a.platform_name for a in adapters]:
        wechat_adapter = next(a for a in adapters if a.platform_name == "wechat")
    else:
        wechat_adapter = None

    if "telegram" in [a.platform_name for a in adapters]:
        telegram_adapter = next(a for a in adapters if a.platform_name == "telegram")
    else:
        telegram_adapter = None

    return MessengerService(
        wechat_adapter=wechat_adapter,
        telegram_adapter=telegram_adapter,
        config=config
    )
