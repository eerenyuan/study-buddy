"""
Monitor 模块 - 监控服务

简化版架构：
┌─────────────────────────────────────────────────┐
│          SimpleMonitorService (监控服务)        │
├─────────────────────────────────────────────────┤
│  - 统一配置文件（JSON）                          │
│  - 自动保存/加载配置                             │
│  - 简化的规则检查（key + regexp）               │
│  - 简化的通知逻辑（should_notify_stop）         │
├─────────────────────────────────────────────────┤
│  SimpleRuleChecker (规则检查器)                 │
│  - 只支持正则表达式匹配                          │
│  - 格式：{"key": "at_desk", "regexp": "^true$"} │
├─────────────────────────────────────────────────┤
│  NotifyManager (通知管理器)                      │
│  - should_notify_stop()                         │
│  - 最小/最大通知间隔                             │
│  - 连续失败限制                                  │
├─────────────────────────────────────────────────┤
│  MonitorConfig (统一配置)                        │
│  - 自动保存/加载                                 │
│  - 包含所有参数                                  │
└─────────────────────────────────────────────────┘

使用示例：
```python
from src.monitor import create_simple_monitor_service

# 创建服务（自动从配置文件加载）
monitor = create_simple_monitor_service(
    vision_analyzer=vision,
    messenger_service=messenger,
    camera_service=camera,
    storage_service=storage,
    config_file="config/monitor_config.json"
)

# 启动监控
monitor.start_monitor()

# 更新配置（自动保存到文件）
monitor.update_config(
    capture_interval=60,
    rules=[{"key": "at_desk", "regexp": "^true$"}]
)
```
"""

from .simple_config import MonitorConfig
from .simple_rule_checker import SimpleRuleChecker, create_simple_rule_checker
from .notify_manager import NotifyManager, NotifyResult, NotifyLevel
from .simple_monitor_service import SimpleMonitorService, MonitorStatus, create_simple_monitor_service

__all__ = [
    'MonitorConfig',
    'SimpleRuleChecker',
    'create_simple_rule_checker',
    'NotifyManager',
    'NotifyResult',
    'NotifyLevel',
    'SimpleMonitorService',
    'MonitorStatus',
    'create_simple_monitor_service',
]
