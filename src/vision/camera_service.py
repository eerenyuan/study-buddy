"""
摄像头服务类（硬件层）

职责：
1. 单次截图：capture() - 同步，立即返回
2. 视频预览：start_preview() / stop_preview()
3. 帧读取：read_preview_frame()
4. 模式管理：stream vs capture

不负责：
- 定时循环
- 业务逻辑
- AI 分析
"""
import threading
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path

from src.common import Logger
from src.vision.camera_singleton import CameraSingleton, CameraMode


@dataclass
class CameraServiceConfig:
    """CameraService 配置对象

    硬件层配置，不包含业务逻辑配置
    """
    # 预览配置
    preview_timeout: int = 300  # 预览客户端超时（秒）

    # 日志配置
    log_dir: str = "logs"


class CameraService:
    """摄像头服务类（硬件层）

    职责：
    1. 单次截图：capture() - 阻塞，立即返回
    2. 视频预览：start_preview() / stop_preview() - 后台线程
    3. 帧读取：read_preview_frame() - 从视频流读取帧
    4. 资源管理：cleanup(), release()

    设计原则：
    - 只管理硬件操作
    - 使用锁保护 stream/capture 切换
    - 不包含业务逻辑（定时、分析、决策等）
    """

    def __init__(self,
                 camera: CameraSingleton,
                 config: CameraServiceConfig):
        """
        Args:
            camera: 摄像头单例实例
            config: 服务配置对象
        """
        self.camera = camera
        self._config = config
        self.logger = Logger(config.log_dir)

        # 模式状态
        self._current_mode: Optional[str] = None  # None | 'capture' | 'preview'
        self._preview_client_id: Optional[str] = None
        self._preview_client_time: Optional[float] = None

        # 线程安全锁（保护 stream/capture 切换）
        self._lock = threading.Lock()

        self.logger.log("camera", "info", "CameraService 初始化（硬件层）")

    @property
    def current_mode(self) -> Optional[str]:
        """获取当前模式（不需要锁：简单读取）"""
        return self._current_mode

    # ==================== 单次截图 ====================

    def capture(self) -> Optional[str]:
        """单次截图（阻塞，立即返回）

        职责：
        1. 切换摄像头到 CAPTURE 模式（如果需要）
        2. 执行截图
        3. 返回图片路径

        线程安全：使用锁保护，与 preview 互斥

        Returns:
            图片路径，失败返回 None
        """
        with self._lock:
            # 切换到 CAPTURE 模式（如果需要）
            if self._current_mode != 'capture':
                if not self.camera.switch_to_mode(CameraMode.CAPTURE):
                    self.logger.log("camera", "error", "切换到 CAPTURE 模式失败")
                    return None
                self._current_mode = 'capture'

            # 执行截图
            try:
                image_path = self.camera.capture()
                if image_path:
                    self.logger.log("camera", "info", f"截图成功: {image_path}")
                else:
                    self.logger.log("camera", "error", "截图失败（返回空路径）")
                return image_path
            except Exception as e:
                self.logger.log("camera", "error", f"截图异常: {e}")
                return None

    # ==================== 视频预览 ====================

    def start_preview(self, client_id: str) -> Dict[str, Any]:
        """启动预览模式（后台线程）

        职责：
        1. 切换摄像头到 STREAM 模式
        2. 记录客户端 ID
        3. 超时自动停止

        线程安全：使用锁保护，与 capture 互斥

        Args:
            client_id: 客户端 ID（用于多客户端协商）

        Returns:
            {"success": bool, "message": str}
        """
        with self._lock:
            # 更新最后客户端
            self._preview_client_id = client_id
            self._preview_client_time = time.time()

            self.logger.log("camera", "info", f"客户端 {client_id} 请求启动预览")

            # 切换到 STREAM 模式（如果需要）
            if self._current_mode != 'preview':
                if not self.camera.switch_to_mode(CameraMode.STREAM):
                    return {"success": False, "message": "摄像头切换失败"}
                self._current_mode = 'preview'

        self.logger.log("camera", "info", "预览模式已启动")
        return {"success": True, "message": "预览模式已启动"}

    def stop_preview(self, client_id: Optional[str] = None) -> Dict[str, Any]:
        """停止预览模式

        Args:
            client_id: 客户端 ID（可选），如果提供则只停止该客户端

        Returns:
            {"success": bool, "message": str}
        """
        with self._lock:
            # 检查客户端 ID（如果提供）
            if client_id is not None and self._preview_client_id != client_id:
                return {"success": False, "message": "不是当前预览客户端"}

            self.logger.log("camera", "info", f"停止预览模式（客户端: {client_id}）")

            # 切换回 CAPTURE 模式（释放摄像头）
            if self._current_mode == 'preview':
                if not self.camera.switch_to_mode(CameraMode.CAPTURE):
                    return {"success": False, "message": "摄像头切换失败"}
                self._current_mode = 'capture'

            # 清除客户端信息
            self._preview_client_id = None
            self._preview_client_time = None

        return {"success": True, "message": "预览模式已停止"}

    def is_preview_client(self, client_id: str) -> bool:
        """检查是否是当前预览客户端

        Args:
            client_id: 客户端 ID

        Returns:
            是否是当前预览客户端
        """
        return self._preview_client_id == client_id

    def is_preview_expired(self) -> bool:
        """检查预览是否超时

        Returns:
            是否超时
        """
        if self._preview_client_time is None:
            return True

        elapsed = time.time() - self._preview_client_time
        return elapsed > self._config.preview_timeout

    def read_preview_frame(self):
        """读取预览帧

        Returns:
            (ret, frame) 元组，失败返回 None
        """
        # 检查模式
        if self._current_mode != 'preview':
            return None

        # 检查超时
        if self.is_preview_expired():
            self.logger.log("camera", "info", "预览超时，自动停止")
            self.stop_preview()
            return None

        return self.camera.read_frame()

    # ==================== 状态查询 ====================

    def get_status(self) -> Dict[str, Any]:
        """获取服务状态

        Returns:
            状态字典
        """
        return {
            "current_mode": self._current_mode,
            "preview_client_id": self._preview_client_id,
            "preview_client_time": self._preview_client_time,
            "preview_expired": self.is_preview_expired() if self._current_mode == 'preview' else None
        }

    # ==================== 资源管理 ====================

    def shutdown(self):
        """关闭服务"""
        self.logger.log("camera", "info", "CameraService 关闭")

        with self._lock:
            # 停止预览
            if self._current_mode == 'preview':
                self.stop_preview()

            # 清除状态
            self._current_mode = None
            self._preview_client_id = None
            self._preview_client_time = None

        # 关闭摄像头
        self.camera.shutdown()


# ==================== 工厂函数 ====================

_service_instance: Optional[CameraService] = None
_service_lock = threading.Lock()


def get_camera_service(camera: CameraSingleton,
                      config: CameraServiceConfig) -> CameraService:
    """获取摄像头服务单例

    Args:
        camera: 摄像头单例实例
        config: 服务配置

    Returns:
        CameraService 单例
    """
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = CameraService(camera, config)
    return _service_instance
