"""
基础类定义
所有模块的抽象基类和通用工具
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
import json


class BaseModule(ABC):
    """所有功能模块的基类"""

    def __init__(self, config):
        self.config = config
        self.enabled = True

    @abstractmethod
    def initialize(self) -> bool:
        """初始化模块"""
        pass

    @abstractmethod
    def shutdown(self):
        """关闭模块"""
        pass


class Analyzer(ABC):
    """分析器基类"""
    @abstractmethod
    def analyze(self, image_data: bytes) -> Dict[str, Any]:
        """分析图像数据"""
        pass


class Notifier(ABC):
    """通知器基类"""
    @abstractmethod
    def notify(self, message: str, level: str = "info") -> bool:
        """发送通知"""
        pass


class Logger:
    """简单日志工具"""

    def __init__(self, log_dir):
        self.log_dir = log_dir

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
        log_file = self.log_dir / f"{datetime.now().strftime('%Y%m%d')}.log"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"写入日志失败: {e}")


class StateManager:
    """状态管理器 - 存储和分析历史状态"""

    def __init__(self):
        self.current_state = {}
        self.history = []
        self.alert_count = {}

    def update_state(self, state: Dict[str, Any]):
        """更新当前状态"""
        self.current_state = state
        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "state": state
        })

        # 保留最近100条记录
        if len(self.history) > 100:
            self.history.pop(0)

    def get_consecutive_count(self, key: str, value: Any) -> int:
        """获取连续某个值的次数"""
        count = 0
        for item in reversed(self.history):
            if item["state"].get(key) == value:
                count += 1
            else:
                break
        return count

    def should_alert(self, alert_key: str, threshold: int) -> bool:
        """判断是否应该触发提醒"""
        current_count = self.alert_count.get(alert_key, 0)
        self.alert_count[alert_key] = current_count + 1
        return self.alert_count[alert_key] >= threshold

    def reset_alert_count(self, alert_key: str):
        """重置提醒计数"""
        self.alert_count[alert_key] = 0
