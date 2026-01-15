"""
通知管理器（替代 DecisionEngine）

职责：
1. 判断是否应该通知
2. 判断是否应该停止服务
3. 维护状态（连续失败次数、最后通知时间）
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta
from enum import Enum

from src.common import Logger


class NotifyLevel(Enum):
    """通知级别"""
    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"


@dataclass
class NotifyResult:
    """通知结果"""
    should_notify: bool           # 是否应该通知
    should_stop: bool             # 是否应该停止服务
    level: NotifyLevel            # 通知级别
    reason: str                   # 原因说明


class NotifyManager:
    """通知管理器

    逻辑：
    1. 如果距离上次通知时间 < min_notify_interval：不通知（即使不合格）
    2. 如果距离上次通知时间 > max_notify_interval：强制通知（即使合格）
    3. 如果连续失败次数 >= consecutive_fail_limit：停止服务
    4. 每次重启服务时，连续失败次数重置为 0
    """

    def __init__(self,
                 min_notify_interval: int = 10,
                 max_notify_interval: int = 60,
                 consecutive_fail_limit: int = 5,
                 log_dir: str = "logs"):
        """
        Args:
            min_notify_interval: 最小通知间隔（分钟）
            max_notify_interval: 最大通知间隔（分钟）
            consecutive_fail_limit: 连续失败次数限制
            log_dir: 日志目录
        """
        self.min_notify_interval = timedelta(minutes=min_notify_interval)
        self.max_notify_interval = timedelta(minutes=max_notify_interval)
        self.consecutive_fail_limit = consecutive_fail_limit
        self.logger = Logger(log_dir)

        # 状态变量
        self.last_notify_time: Optional[datetime] = None
        self.consecutive_failures = 0

        self.logger.log("notify_manager", "info",
                       f"NotifyManager 初始化 - min_interval={min_notify_interval}min, "
                       f"max_interval={max_notify_interval}min, fail_limit={consecutive_fail_limit}")

    def should_notify_stop(self, is_valid: bool) -> NotifyResult:
        """判断是否应该通知、是否应该停止服务

        Args:
            is_valid: 当前检查是否合格

        Returns:
            NotifyResult 对象
        """
        now = datetime.now()

        # 1. 检查是否应该停止服务（连续失败次数）
        if self.consecutive_failures >= self.consecutive_fail_limit:
            self.logger.log("notify_manager", "warning",
                           f"连续失败次数达到限制 ({self.consecutive_failures})，停止服务")
            return NotifyResult(
                should_notify=False,
                should_stop=True,
                level=NotifyLevel.DANGER,
                reason=f"连续失败 {self.consecutive_failures} 次，已达到限制"
            )

        # 2. 更新连续失败计数
        if is_valid:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1

        # 3. 检查通知间隔
        if self.last_notify_time is None:
            # 第一次，总是通知
            self.last_notify_time = now
            level = NotifyLevel.WARNING if not is_valid else NotifyLevel.INFO
            return NotifyResult(
                should_notify=True,
                should_stop=False,
                level=level,
                reason="首次检查" if is_valid else "首次检查，发现问题"
            )

        time_since_last_notify = now - self.last_notify_time

        # 4. 如果距离上次通知时间太短，不通知
        if time_since_last_notify < self.min_notify_interval:
            self.logger.log("notify_manager", "info",
                           f"距离上次通知时间太短 ({time_since_last_notify.seconds}s)，不通知")
            return NotifyResult(
                should_notify=False,
                should_stop=False,
                level=NotifyLevel.INFO,
                reason=f"距离上次通知仅 {time_since_last_notify.seconds}s，小于最小间隔"
            )

        # 5. 如果距离上次通知时间太久，强制通知
        if time_since_last_notify > self.max_notify_interval:
            self.last_notify_time = now
            self.logger.log("notify_manager", "info",
                           f"距离上次通知时间太久 ({time_since_last_notify.seconds}s)，强制通知")
            return NotifyResult(
                should_notify=True,
                should_stop=False,
                level=NotifyLevel.INFO,
                reason=f"更新状态 - {'正常' if is_valid else '仍有问题'}"
            )

        # 6. 正常情况：如果不合格，通知
        if not is_valid:
            self.last_notify_time = now
            return NotifyResult(
                should_notify=True,
                should_stop=False,
                level=NotifyLevel.WARNING,
                reason=f"连续失败 {self.consecutive_failures} 次"
            )

        # 7. 合格且在时间范围内，不通知
        return NotifyResult(
            should_notify=False,
            should_stop=False,
            level=NotifyLevel.INFO,
            reason="状态正常"
        )

    def reset(self):
        """重置状态（用于重启服务时）"""
        self.consecutive_failures = 0
        self.last_notify_time = None
        self.logger.log("notify_manager", "info", "状态已重置")

    def update_config(self,
                     min_notify_interval: int = None,
                     max_notify_interval: int = None,
                     consecutive_fail_limit: int = None):
        """更新配置

        Args:
            min_notify_interval: 最小通知间隔（分钟）
            max_notify_interval: 最大通知间隔（分钟）
            consecutive_fail_limit: 连续失败次数限制
        """
        if min_notify_interval is not None:
            self.min_notify_interval = timedelta(minutes=min_notify_interval)
            self.logger.log("notify_manager", "info",
                           f"配置已更新: min_notify_interval = {min_notify_interval}")

        if max_notify_interval is not None:
            self.max_notify_interval = timedelta(minutes=max_notify_interval)
            self.logger.log("notify_manager", "info",
                           f"配置已更新: max_notify_interval = {max_notify_interval}")

        if consecutive_fail_limit is not None:
            self.consecutive_fail_limit = consecutive_fail_limit
            self.logger.log("notify_manager", "info",
                           f"配置已更新: consecutive_fail_limit = {consecutive_fail_limit}")

    def get_status(self) -> dict:
        """获取状态"""
        return {
            "consecutive_failures": self.consecutive_failures,
            "consecutive_fail_limit": self.consecutive_fail_limit,
            "last_notify_time": self.last_notify_time.isoformat() if self.last_notify_time else None,
            "min_notify_interval_minutes": int(self.min_notify_interval.total_seconds() / 60),
            "max_notify_interval_minutes": int(self.max_notify_interval.total_seconds() / 60)
        }
