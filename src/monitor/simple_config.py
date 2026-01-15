"""
Monitor 简化配置

所有参数统一为 key:value 格式，保存到 JSON 文件
"""
import json
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime


@dataclass
class MonitorConfig:
    """Monitor 统一配置

    所有参数都保存在一个 JSON 文件中
    """
    # 规则配置（RuleChecker 用）
    rules: List[Dict[str, str]] = field(default_factory=list)

    # 通知相关参数
    min_notify_interval: int = 10       # 最小通知间隔（分钟）- 如果上次通知时间太短，不通知
    max_notify_interval: int = 60       # 最大通知间隔（分钟）- 如果上次通知时间太久，强制通知
    consecutive_fail_limit: int = 5     # 连续失败次数限制 - 超过后停止服务

    # 监控时间相关
    auto_start_time: Optional[str] = None   # 每日自动开始时间（HH:MM 格式）
    auto_stop_time: Optional[str] = None    # 每日自动停止时间（HH:MM 格式）
    enable_time_scheduler: bool = False     # 是否启用时间调度

    # 监控参数
    capture_interval: int = 30              # 截图间隔（秒）
    preview_duration: int = 10             # 预览时长（秒）
    enable_preview: bool = True            # 是否启用预览

    # 日志目录
    log_dir: str = "logs"

    # 配置文件路径（内部使用）
    _config_file: Optional[str] = field(default=None, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "rules": self.rules,
            "min_notify_interval": self.min_notify_interval,
            "max_notify_interval": self.max_notify_interval,
            "consecutive_fail_limit": self.consecutive_fail_limit,
            "auto_start_time": self.auto_start_time,
            "auto_stop_time": self.auto_stop_time,
            "enable_time_scheduler": self.enable_time_scheduler,
            "capture_interval": self.capture_interval,
            "preview_duration": self.preview_duration,
            "enable_preview": self.enable_preview,
            "log_dir": self.log_dir
        }

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any], config_file: str = None) -> 'MonitorConfig':
        """从字典创建配置

        Args:
            config_dict: 配置字典
            config_file: 配置文件路径（用于后续自动保存）

        Returns:
            MonitorConfig 实例
        """
        # 辅助函数：安全转换为整数
        def to_int(value, default):
            if value is None:
                return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default

        return cls(
            rules=config_dict.get("rules", []),
            min_notify_interval=to_int(config_dict.get("min_notify_interval"), 10),
            max_notify_interval=to_int(config_dict.get("max_notify_interval"), 60),
            consecutive_fail_limit=to_int(config_dict.get("consecutive_fail_limit"), 5),
            auto_start_time=config_dict.get("auto_start_time"),
            auto_stop_time=config_dict.get("auto_stop_time"),
            enable_time_scheduler=config_dict.get("enable_time_scheduler", False),
            capture_interval=to_int(config_dict.get("capture_interval"), 30),
            preview_duration=to_int(config_dict.get("preview_duration"), 10),
            enable_preview=config_dict.get("enable_preview", True),
            log_dir=config_dict.get("log_dir", "logs"),
            _config_file=config_file
        )

    def save(self):
        """保存配置到文件"""
        if self._config_file:
            config_file = Path(self._config_file)
            config_file.parent.mkdir(parents=True, exist_ok=True)

            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    def update(self, **kwargs):
        """更新配置并自动保存

        Args:
            **kwargs: 要更新的配置项
        """
        for key, value in kwargs.items():
            if hasattr(self, key) and not key.startswith("_"):
                # 类型转换：数值字段需要转换为整数
                if key in ["min_notify_interval", "max_notify_interval", "consecutive_fail_limit",
                          "capture_interval", "preview_duration"]:
                    if value is not None and value != "":
                        value = int(value)
                # 布尔字段转换
                elif key in ["enable_preview", "enable_time_scheduler"]:
                    if isinstance(value, str):
                        value = value.lower() in ('true', '1', 'yes')

                setattr(self, key, value)

        # 自动保存
        self.save()

    @classmethod
    def load(cls, config_file: str) -> 'MonitorConfig':
        """从文件加载配置

        Args:
            config_file: 配置文件路径

        Returns:
            MonitorConfig 实例
        """
        config_path = Path(config_file)

        # 如果文件不存在，创建默认配置文件
        if not config_path.exists():
            default_config = cls.get_default()
            default_config._config_file = config_file
            default_config.save()
            return default_config

        # 加载配置
        with open(config_path, "r", encoding="utf-8") as f:
            config_dict = json.load(f)

        return cls.from_dict(config_dict, config_file)

    @classmethod
    def get_default(cls) -> 'MonitorConfig':
        """获取默认配置"""
        return cls(
            rules=[
                {"key": "at_desk", "regexp": "^true$"},
                {"key": "is_study", "regexp": "^true$"},
                {"key": "activity", "regexp": "^(看书|写字)$"},
                {"key": "posture", "regexp": "^(端正)$"},
                {"key": "lighting", "regexp": "^(充足|一般)$"}
            ],
            min_notify_interval=10,
            max_notify_interval=60,
            consecutive_fail_limit=5,
            auto_start_time="09:00",
            auto_stop_time="18:00",
            enable_time_scheduler=False,
            capture_interval=30,
            preview_duration=10,
            enable_preview=True,
            log_dir="logs"
        )
