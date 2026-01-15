"""
通用工具类
"""
import os
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from dataclasses import dataclass

# 项目根目录
BASE_DIR = Path(__file__).parent.parent

# 加载 .env 文件
load_dotenv(os.path.join(BASE_DIR, '.env'))


class Logger:
    """简单日志工具"""

    def __init__(self, log_dir):
        self.log_dir = Path(log_dir)

    def log(self, module: str, level: str, message: str, **kwargs):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "module": module,
            "level": level,
            "message": message,
            **kwargs
        }

        # 输出到控制台
        print(f"[{timestamp}] [{module}] {level}: {message}")

        # 输出到文件（可选）
        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            log_file = self.log_dir / f"{datetime.now().strftime('%Y%m%d')}.log"
            try:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            except Exception as e:
                print(f"写入日志失败: {e}")


@dataclass
class KimiConfig:
    """Kimi Vision API 配置"""
    api_key: str
    base_url: str = "https://api.moonshot.cn/v1"
    model: str = "moonshot-v1-8k-vision-preview"
    timeout: int = 120


@dataclass
class CameraConfig:
    """摄像头配置"""
    capture_interval: int = 60  # 秒
    camera_index: int = 0
    resolution: tuple = (1920, 1080)  # 目标分辨率
    quality: int = 85  # JPEG 质量


@dataclass
class WeChatConfig:
    """企业微信配置"""
    corpid: str
    agentid: str
    secret: str
    touser: str  # 支持多个用户，用 | 分隔，例如 "RenYuan|xiaoyu"


@dataclass
class TelegramConfig:
    """Telegram 配置（可选）"""
    bot_token: str = ""
    chat_id: str = ""


@dataclass
class SchedulerConfig:
    """调度器配置"""
    alert_threshold: int = 3  # 连续多少次触发才提醒
    focus_score_threshold: int = 5  # 1-10分
    check_interval: int = 60  # 检查间隔


class Config:
    """全局配置类"""

    def __init__(self):
        # Kimi 配置
        self.kimi = KimiConfig(
            api_key=os.getenv("KIMI_API_KEY", ""),
            base_url=os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1"),
            model=os.getenv("KIMI_MODEL", "moonshot-v1-8k-vision-preview"),
            timeout=int(os.getenv("KIMI_TIMEOUT", "120"))
        )

        # 摄像头配置
        self.camera = CameraConfig(
            capture_interval=int(os.getenv("CAPTURE_INTERVAL", "60")),
            camera_index=int(os.getenv("CAMERA_INDEX", "0")),
            resolution=tuple(map(int, os.getenv("RESOLUTION", "1920,1080").split(","))),
            quality=int(os.getenv("IMAGE_QUALITY", "85"))
        )

        # 企业微信配置
        self.wechat = WeChatConfig(
            corpid=os.getenv("WECHAT_CORPID", ""),
            agentid=os.getenv("WECHAT_AGENTID", ""),
            secret=os.getenv("WECHAT_SECRET", ""),
            touser=os.getenv("WECHAT_TOUSER", "")
        )

        # Telegram 配置
        self.telegram = TelegramConfig(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            chat_id=os.getenv("TELEGRAM_CHAT_ID", "")
        )

        # 调度器配置
        self.scheduler = SchedulerConfig(
            alert_threshold=int(os.getenv("ALERT_THRESHOLD", "3")),
            focus_score_threshold=int(os.getenv("FOCUS_SCORE_THRESHOLD", "5")),
            check_interval=int(os.getenv("CHECK_INTERVAL", "60"))
        )

        # 项目路径
        self.log_dir = BASE_DIR / "logs"
        self.log_dir.mkdir(exist_ok=True)


# 全局配置实例
config = Config()
