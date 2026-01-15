"""
Vision 模块 - 已重构版本

架构：显式依赖注入，使用配置对象

包含：
- CameraSingleton: 单例摄像头管理类（硬件层）
- CameraService: 摄像头服务类（业务层）
- CameraServiceConfig: 服务配置对象（配置层）

分层架构：
┌─────────────────────────────────────┐
│     Web Layer (Flask Routes)        │  ← HTTP 请求处理
├─────────────────────────────────────┤
│     CameraService (业务层)          │  ← 业务逻辑协调
│     - start_monitor()               │
│     - start_preview()               │
├─────────────────────────────────────┤
│     CameraServiceConfig (配置层)    │  ← 显式依赖注入
│     - capture_interval              │
│     - capture_callback              │
├─────────────────────────────────────┤
│     CameraSingleton (硬件层)         │  ← 只管理摄像头硬件
│     - switch_to_mode()              │
│     - capture()                     │
│     - read_frame()                  │
└─────────────────────────────────────┘
"""

from .camera_singleton import (
    get_camera_singleton,
    CameraSingleton,
    CameraMode
)

from .camera_service import (
    get_camera_service,
    CameraService,
    CameraServiceConfig
)

__all__ = [
    # 硬件层
    'get_camera_singleton',
    'CameraSingleton',
    'CameraMode',

    # 配置层
    'CameraServiceConfig',

    # 服务层
    'get_camera_service',
    'CameraService',
]
