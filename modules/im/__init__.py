"""
IM 模块 - 负责向家长发送通知
支持企业微信和 Telegram
"""
from typing import Dict, Any
import time
import httpx
import os
from pathlib import Path
from core.base import BaseModule, Notifier, Logger
from core.config import Config


class WeChatNotifier(BaseModule, Notifier):
    """企业微信通知器"""

    def __init__(self, config: Config):
        super().__init__(config)
        self.logger = Logger(config.log_dir)
        self.access_token = None
        self.token_expires_at = 0

    def initialize(self) -> bool:
        """初始化通知器"""
        self.logger.log("im", "info", f"企业微信初始化 - 接收人: {self.config.wechat.touser}")
        return True

    def shutdown(self):
        """关闭通知器"""
        self.logger.log("im", "info", "企业微信通知器已关闭")

    def notify(self, message: str, level: str = "info") -> bool:
        """发送通知

        Args:
            message: 消息内容
            level: 消息级别 (info/warning/danger)

        Returns:
            是否发送成功
        """
        # 所有消息都使用文本消息（简单可靠）
        return self._send_text(message)

    def _get_access_token(self) -> str:
        """获取访问令牌（带缓存）"""
        # 如果缓存有效，直接返回
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token

        # 获取新令牌
        url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        params = {
            "corpid": self.config.wechat.corpid,
            "corpsecret": self.config.wechat.secret
        }

        response = httpx.get(url, params=params, timeout=30)
        data = response.json()

        if data.get("errcode") == 0:
            self.access_token = data["access_token"]
            # 提前5分钟过期
            self.token_expires_at = time.time() + data["expires_in"] - 300
            self.logger.log("im", "info", "获取 access_token 成功")
            return self.access_token
        else:
            error_msg = data.get("errmsg", "未知错误")
            self.logger.log("im", "error", f"获取 access_token 失败: {error_msg}")
            raise Exception(f"获取 access_token 失败: {error_msg}")

    def _send_text(self, content: str, touser: str = None) -> bool:
        """发送文本消息

        Args:
            content: 消息内容
            touser: 接收人，默认使用配置中的用户（支持多个，用 | 分隔）

        Returns:
            是否发送成功
        """
        access_token = self._get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"

        # 获取收件人列表
        recipients = touser or self.config.wechat.touser

        # 如果包含多个收件人，分别发送
        users = [u.strip() for u in recipients.split("|") if u.strip()]
        all_success = True

        for user in users:
            data = {
                "touser": user,
                "msgtype": "text",
                "agentid": int(self.config.wechat.agentid),
                "text": {"content": content},
                "safe": 0
            }

            response = httpx.post(url, json=data, timeout=30)
            result = response.json()

            if result.get("errcode") == 0:
                self.logger.log("im", "info", f"发送文本消息成功到 {user}")
            else:
                error_msg = result.get("errmsg", "未知错误")
                self.logger.log("im", "error", f"发送文本消息失败到 {user}: {error_msg}")
                all_success = False

        return all_success

    def _send_text_card(self, title: str, description: str, url: str = "", touser: str = None) -> bool:
        """发送文本卡片消息

        Args:
            title: 标题
            description: 描述
            url: 跳转链接
            touser: 接收人

        Returns:
            是否发送成功
        """
        access_token = self._get_access_token()
        api_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"

        data = {
            "touser": touser or self.config.wechat.touser,
            "msgtype": "textcard",
            "agentid": int(self.config.wechat.agentid),
            "textcard": {
                "title": title,
                "description": description,
                "url": url,
                "btntxt": "查看详情"
            }
        }

        response = httpx.post(api_url, json=data, timeout=30)
        result = response.json()

        if result.get("errcode") == 0:
            self.logger.log("im", "info", f"发送文本卡片成功: {title}")
            return True
        else:
            error_msg = result.get("errmsg", "未知错误")
            self.logger.log("im", "error", f"发送文本卡片失败: {error_msg}")
            return False

    def _send_markdown(self, content: str, touser: str = None) -> bool:
        """发送 Markdown 消息

        Args:
            content: Markdown 内容
            touser: 接收人

        Returns:
            是否发送成功
        """
        access_token = self._get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"

        data = {
            "touser": touser or self.config.wechat.touser,
            "msgtype": "markdown",
            "agentid": int(self.config.wechat.agentid),
            "markdown": {"content": content}
        }

        response = httpx.post(url, json=data, timeout=30)
        result = response.json()

        if result.get("errcode") == 0:
            self.logger.log("im", "info", "发送 Markdown 消息成功")
            return True
        else:
            error_msg = result.get("errmsg", "未知错误")
            self.logger.log("im", "error", f"发送 Markdown 消息失败: {error_msg}")
            return False

    def send_image(self, image_path: str) -> bool:
        """发送图片消息

        Args:
            image_path: 图片文件路径

        Returns:
            是否发送成功
        """
        if not Path(image_path).exists():
            self.logger.log("im", "error", f"图片文件不存在: {image_path}")
            return False

        # 检查文件大小（不超过2MB）
        file_size = os.path.getsize(image_path)
        if file_size > 2 * 1024 * 1024:
            self.logger.log("im", "error", f"图片大小超过2MB限制: {file_size / 1024 / 1024:.2f}MB")
            return False

        try:
            # 步骤1: 上传图片（只需上传一次）
            access_token = self._get_access_token()
            upload_url = f"https://qyapi.weixin.qq.com/cgi-bin/media/upload?access_token={access_token}&type=image"

            with open(image_path, "rb") as f:
                files = {"media": (Path(image_path).name, f, "image/jpeg")}
                response = httpx.post(upload_url, files=files, timeout=30)

            upload_result = response.json()
            if upload_result.get("errcode") != 0:
                self.logger.log("im", "error", f"上传图片失败: {upload_result.get('errmsg')}")
                return False

            media_id = upload_result.get("media_id")
            self.logger.log("im", "info", f"上传图片成功: media_id={media_id}")

            # 步骤2: 发送图片消息给所有用户
            send_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"

            # 获取收件人列表
            recipients = self.config.wechat.touser
            users = [u.strip() for u in recipients.split("|") if u.strip()]
            all_success = True

            for user in users:
                data = {
                    "touser": user,
                    "msgtype": "image",
                    "agentid": int(self.config.wechat.agentid),
                    "image": {"media_id": media_id},
                    "safe": 0
                }

                response = httpx.post(send_url, json=data, timeout=30)
                result = response.json()

                if result.get("errcode") == 0:
                    self.logger.log("im", "info", f"发送图片成功到 {user}")
                else:
                    error_msg = result.get("errmsg", "未知错误")
                    self.logger.log("im", "error", f"发送图片失败到 {user}: {error_msg}")
                    all_success = False

            return all_success

        except Exception as e:
            self.logger.log("im", "error", f"发送图片异常: {e}")
            return False


class TelegramNotifier(BaseModule, Notifier):
    """Telegram 通知器（可选）"""

    def __init__(self, config: Config):
        super().__init__(config)
        self.logger = Logger(config.log_dir)
        self.enabled = bool(config.telegram.bot_token and config.telegram.chat_id)

    def initialize(self) -> bool:
        """初始化通知器"""
        if not self.enabled:
            self.logger.log("im", "info", "Telegram 未配置，跳过初始化")
            return False

        self.logger.log("im", "info", f"Telegram 初始化 - Chat ID: {self.config.telegram.chat_id}")
        return True

    def shutdown(self):
        """关闭通知器"""
        if self.enabled:
            self.logger.log("im", "info", "Telegram 通知器已关闭")

    def notify(self, message: str, level: str = "info") -> bool:
        """发送通知

        Args:
            message: 消息内容
            level: 消息级别

        Returns:
            是否发送成功
        """
        if not self.enabled:
            self.logger.log("im", "warning", "Telegram 未配置，无法发送消息")
            return False

        # 根据级别添加表情符号
        emoji = {
            "danger": "🚨",
            "warning": "⚠️",
            "info": "📝"
        }
        prefix = emoji.get(level, "")

        url = f"https://api.telegram.org/bot{self.config.telegram.bot_token}/sendMessage"
        data = {
            "chat_id": self.config.telegram.chat_id,
            "text": f"{prefix} {message}",
            "parse_mode": "Markdown"
        }

        try:
            response = httpx.post(url, json=data, timeout=30)
            result = response.json()

            if result.get("ok"):
                self.logger.log("im", "info", "Telegram 消息发送成功")
                return True
            else:
                error_desc = result.get("description", "未知错误")
                self.logger.log("im", "error", f"Telegram 消息发送失败: {error_desc}")
                return False
        except Exception as e:
            self.logger.log("im", "error", f"Telegram 消息发送异常: {e}")
            return False


class IMManager(BaseModule):
    """IM 管理器 - 统一管理多个通知渠道"""

    def __init__(self, config: Config):
        super().__init__(config)
        self.logger = Logger(config.log_dir)
        self.notifiers = []

    def initialize(self) -> bool:
        """初始化所有通知器"""
        self.logger.log("im", "info", "初始化 IM 管理器")

        # 添加企业微信通知器
        wechat = WeChatNotifier(self.config)
        if wechat.initialize():
            self.notifiers.append(wechat)

        # 添加 Telegram 通知器（如果配置了）
        telegram = TelegramNotifier(self.config)
        if telegram.initialize():
            self.notifiers.append(telegram)

        self.logger.log("im", "info", f"已加载 {len(self.notifiers)} 个通知器")
        return len(self.notifiers) > 0

    def shutdown(self):
        """关闭所有通知器"""
        for notifier in self.notifiers:
            notifier.shutdown()
        self.logger.log("im", "info", "IM 管理器已关闭")

    def notify(self, message: str, level: str = "info") -> bool:
        """通过所有渠道发送通知

        Args:
            message: 消息内容
            level: 消息级别

        Returns:
            是否有任意一个发送成功
        """
        success = False
        for notifier in self.notifiers:
            try:
                if notifier.notify(message, level):
                    success = True
            except Exception as e:
                self.logger.log("im", "error", f"通知器异常: {e}")

        return success

    def notify_all(self, message: str, level: str = "info") -> Dict[str, bool]:
        """通过所有渠道发送通知，返回每个渠道的结果

        Args:
            message: 消息内容
            level: 消息级别

        Returns:
            每个通知器的发送结果
        """
        results = {}
        for notifier in self.notifiers:
            try:
                notifier_name = notifier.__class__.__name__
                results[notifier_name] = notifier.notify(message, level)
            except Exception as e:
                self.logger.log("im", "error", f"通知器异常: {e}")
                results[notifier.__class__.__name__] = False

        return results

    def send_image(self, image_path: str) -> bool:
        """发送图片到所有支持图片的通知器

        Args:
            image_path: 图片文件路径

        Returns:
            是否有任意一个发送成功
        """
        success = False
        for notifier in self.notifiers:
            try:
                # 只支持企业微信发送图片
                if hasattr(notifier, 'send_image'):
                    if notifier.send_image(image_path):
                        success = True
            except Exception as e:
                self.logger.log("im", "error", f"发送图片异常: {e}")

        return success


def create_im_module(config: Config):
    """创建 IM 模块工厂函数"""
    return IMManager(config)
