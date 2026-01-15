"""
企业微信消息适配器

支持发送文本、Markdown、图片、卡片消息
未来可以扩展支持接收消息（通过回调接口）
"""
import time
import os
from typing import Optional
from pathlib import Path

import httpx

from .base_adapter import MessageAdapter
from ..models.message import MessageType


class WeChatAdapter(MessageAdapter):
    """企业微信适配器

    功能：
    1. 发送文本消息
    2. 发送 Markdown 消息
    3. 发送图片消息
    4. 发送文本卡片消息

    未来扩展：
    - 接收消息（通过企业微信回调）
    - 交互按钮（卡片消息的按钮）
    """

    def __init__(self,
                 corpid: str,
                 corpsecret: str,
                 agentid: str,
                 log_dir: str = "logs"):
        """
        Args:
            corpid: 企业 ID
            corpsecret: 应用 Secret
            agentid: 应用 ID
            log_dir: 日志目录
        """
        super().__init__("wechat", log_dir)
        self.corpid = corpid
        self.corpsecret = corpsecret
        self.agentid = agentid

        # Token 缓存
        self.access_token: Optional[str] = None
        self.token_expires_at: float = 0

    def initialize(self) -> bool:
        """初始化适配器"""
        self.logger.log("messenger", "info",
                       f"企业微信初始化 - corpid: {self.corpid}, agentid: {self.agentid}")
        return True

    def shutdown(self):
        """关闭适配器"""
        self.access_token = None
        self.token_expires_at = 0
        self.logger.log("messenger", "info", "企业微信适配器已关闭")

    # ==================== Token 管理 ====================

    def _get_access_token(self) -> str:
        """获取访问令牌（带缓存）"""
        # 如果缓存有效，直接返回
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token

        # 获取新令牌
        url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        params = {
            "corpid": self.corpid,
            "corpsecret": self.corpsecret
        }

        try:
            response = httpx.get(url, params=params, timeout=30)
            data = response.json()

            if data.get("errcode") == 0:
                self.access_token = data["access_token"]
                # 提前5分钟过期
                self.token_expires_at = time.time() + data["expires_in"] - 300
                self.logger.log("messenger", "info", "获取 access_token 成功")
                return self.access_token
            else:
                error_msg = data.get("errmsg", "未知错误")
                self.logger.log("messenger", "error", f"获取 access_token 失败: {error_msg}")
                raise Exception(f"获取 access_token 失败: {error_msg}")

        except Exception as e:
            self.logger.log("messenger", "error", f"获取 access_token 异常: {e}")
            raise

    # ==================== 发送消息 ====================

    def send_text(self, content: str, recipient_id: str) -> bool:
        """发送文本消息"""
        access_token = self._get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}&debug=1"

        # 支持多个接收人
        users = [u.strip() for u in recipient_id.split("|") if u.strip()]
        all_success = True

        for user in users:
            data = {
                "touser": user,
                "msgtype": "text",
                "agentid": int(self.agentid),
                "text": {"content": content},
                "safe": 0
            }

            try:
                response = httpx.post(url, json=data, timeout=30)
                result = response.json()

                if result.get("errcode") == 0:
                    self.logger.log("messenger", "info", f"发送文本消息成功到 {user}")
                else:
                    error_msg = result.get("errmsg", "未知错误")
                    self.logger.log("messenger", "error", f"发送文本消息失败到 {user}: {error_msg}")
                    all_success = False

            except Exception as e:
                self.logger.log("messenger", "error", f"发送文本消息异常: {e}")
                all_success = False

        return all_success

    def send_markdown(self, content: str, recipient_id: str) -> bool:
        """发送 Markdown 消息"""
        access_token = self._get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}&debug=1"

        data = {
            "touser": recipient_id,
            "msgtype": "markdown",
            "agentid": int(self.agentid),
            "markdown": {"content": content}
        }

        try:
            response = httpx.post(url, json=data, timeout=30)
            result = response.json()

            if result.get("errcode") == 0:
                self.logger.log("messenger", "info", "发送 Markdown 消息成功")
                return True
            else:
                error_msg = result.get("errmsg", "未知错误")
                self.logger.log("messenger", "error", f"发送 Markdown 消息失败: {error_msg}")
                return False

        except Exception as e:
            self.logger.log("messenger", "error", f"发送 Markdown 消息异常: {e}")
            return False

    def send_image(self, image_path: str, recipient_id: str) -> bool:
        """发送图片消息"""
        print(f"[DEBUG send_image] image_path: {image_path}")
        print(f"[DEBUG send_image] exists: {Path(image_path).exists()}")

        if not Path(image_path).exists():
            self.logger.log("messenger", "error", f"图片文件不存在: {image_path}")
            return False

        # 检查文件大小（不超过2MB）
        file_size = os.path.getsize(image_path)
        print(f"[DEBUG send_image] file_size: {file_size} bytes")
        if file_size > 2 * 1024 * 1024:
            self.logger.log("messenger", "error", f"图片大小超过2MB限制: {file_size / 1024 / 1024:.2f}MB")
            return False

        try:
            # 步骤1: 上传图片
            access_token = self._get_access_token()
            upload_url = f"https://qyapi.weixin.qq.com/cgi-bin/media/upload?access_token={access_token}&type=image&debug=1"

            print(f"[DEBUG send_image] 开始上传图片: {image_path}")
            with open(image_path, "rb") as f:
                files = {"media": (Path(image_path).name, f, "image/jpeg")}
                response = httpx.post(upload_url, files=files, timeout=30)

            upload_result = response.json()
            print(f"[DEBUG send_image] upload_result: {upload_result}")

            if upload_result.get("errcode") != 0:
                error_msg = upload_result.get('errmsg', '未知错误')
                self.logger.log("messenger", "error", f"上传图片失败: {error_msg}")
                print(f"[DEBUG send_image] 上传失败: errcode={upload_result.get('errcode')}, errmsg={error_msg}")
                return False

            media_id = upload_result.get("media_id")
            self.logger.log("messenger", "info", f"上传图片成功: media_id={media_id}")
            print(f"[DEBUG send_image] 上传成功，media_id: {media_id}")

            # 步骤2: 发送图片消息
            send_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}&debug=1"

            users = [u.strip() for u in recipient_id.split("|") if u.strip()]
            all_success = True

            for user in users:
                data = {
                    "touser": user,
                    "msgtype": "image",
                    "agentid": int(self.agentid),
                    "image": {"media_id": media_id},
                    "safe": 0
                }

                response = httpx.post(send_url, json=data, timeout=30)
                result = response.json()

                if result.get("errcode") == 0:
                    self.logger.log("messenger", "info", f"发送图片成功到 {user}")
                else:
                    error_msg = result.get("errmsg", "未知错误")
                    self.logger.log("messenger", "error", f"发送图片失败到 {user}: {error_msg}")
                    all_success = False

            return all_success

        except Exception as e:
            self.logger.log("messenger", "error", f"发送图片异常: {e}")
            return False

    def send_card(self, title: str, description: str, url: str, recipient_id: str) -> bool:
        """发送文本卡片消息"""
        access_token = self._get_access_token()
        api_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"

        data = {
            "touser": recipient_id,
            "msgtype": "textcard",
            "agentid": int(self.agentid),
            "textcard": {
                "title": title,
                "description": description,
                "url": url,
                "btntxt": "查看详情"
            }
        }

        try:
            response = httpx.post(api_url, json=data, timeout=30)
            result = response.json()

            if result.get("errcode") == 0:
                self.logger.log("messenger", "info", f"发送文本卡片成功: {title}")
                return True
            else:
                error_msg = result.get("errmsg", "未知错误")
                self.logger.log("messenger", "error", f"发送文本卡片失败: {error_msg}")
                return False

        except Exception as e:
            self.logger.log("messenger", "error", f"发送文本卡片异常: {e}")
            return False
