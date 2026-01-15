"""
单例摄像头管理类
确保全局只有一个摄像头实例，支持模式切换
"""
import threading
import time
import cv2
from pathlib import Path
from typing import Optional, Literal
from datetime import datetime

from src.common import Config
from src.common import Logger


class CameraMode:
    """摄像头模式"""
    CAPTURE = "capture"  # 截图模式
    STREAM = "stream"    # 视频流模式


class CameraSingleton:
    """单例摄像头类

    职责：
    1. 硬件管理（打开、关闭摄像头）
    2. 模式管理（截图模式 vs 视频流模式）
    3. 基本操作（capture、read_frame）
    4. 模式切换延迟处理
    """

    _instance: Optional['CameraSingleton'] = None
    _lock = threading.Lock()

    def __new__(cls, config: Config):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Config):
        if self._initialized:
            return

        self.config = config
        self.logger = Logger(config.log_dir)
        self.cap: Optional[cv2.VideoCapture] = None
        self.mode: Optional[str] = None
        self.mode_lock = threading.Lock()
        self.last_frame = None
        self.last_frame_time = None

        # 模式切换配置
        self.switch_delay = 0.5  # 切换模式时的等待时间（秒）

        # 项目根目录（用于构建绝对路径）
        self.project_root = Path(__file__).parent.parent.parent

        self._initialized = True
        self.logger.log("camera", "info", "单例摄像头管理器创建")

    def switch_to_mode(self, target_mode: str) -> bool:
        """切换到指定模式（自动处理切换延迟）

        Args:
            target_mode: 目标模式 (CameraMode.CAPTURE 或 CameraMode.STREAM)

        Returns:
            是否切换成功
        """
        with self.mode_lock:
            # 如果已经是目标模式，直接返回
            if self.mode == target_mode and self.cap is not None and self.cap.isOpened():
                self.logger.log("camera", "info", f"摄像头已经是 {target_mode} 模式")
                return True

            # 需要切换模式：先关闭
            if self.cap is not None:
                self.logger.log("camera", "info", f"切换模式: {self.mode or '未初始化'} -> {target_mode}")
                self.cap.release()
                self.cap = None
                self.mode = None

        # 释放锁后等待，避免阻塞其他操作
        if self.mode is not None:
            time.sleep(self.switch_delay)

        # 重新初始化为目标模式
        with self.mode_lock:
            try:
                self.cap = cv2.VideoCapture(self.config.camera.camera_index)

                if not self.cap.isOpened():
                    self.logger.log("camera", "error", f"无法打开摄像头 (索引: {self.config.camera.camera_index})")
                    return False

                # 设置分辨率
                width, height = self.config.camera.resolution
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

                # 设置缓冲区大小
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                self.mode = target_mode
                self.logger.log("camera", "info", f"摄像头切换成功 - 模式: {target_mode}, 索引: {self.config.camera.camera_index}")
                return True

            except Exception as e:
                self.logger.log("camera", "error", f"摄像头初始化失败: {e}")
                return False

    def get_mode(self) -> Optional[str]:
        """获取当前模式"""
        with self.mode_lock:
            return self.mode

    def is_mode(self, mode: str) -> bool:
        """检查当前是否为指定模式"""
        return self.get_mode() == mode

    def capture(self, output_path: str = None) -> Optional[str]:
        """捕获单张图像

        注意：不需要锁，因为：
        1. capture() 和 read_frame() 不会同时调用（模式互斥）
        2. cap.read() 本身是线程安全的（OpenCV 内部有锁）

        Args:
            output_path: 输出文件路径

        Returns:
            图片文件路径，失败返回 None
        """
        if self.cap is None or not self.cap.isOpened():
            self.logger.log("camera", "error", "摄像头未初始化")
            return None

        try:
            # 清空缓冲区：读取并丢弃2帧
            for _ in range(2):
                self.cap.read()

            # 读取最新帧（OpenCV 内部线程安全）
            ret, frame = self.cap.read()
            if not ret:
                self.logger.log("camera", "error", "无法从摄像头读取图像")
                return None

            # 生成文件名（格式：月日年 时分秒，例如 01152026 153045）
            if output_path is None:
                timestamp = datetime.now()
                output_path = self.project_root / "data" / "captures" / f"{timestamp.strftime('%m%d%Y %H%M%S')}.jpg"
                output_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                # 如果是相对路径，转换为绝对路径
                output_path = Path(output_path)
                if not output_path.is_absolute():
                    output_path = self.project_root / output_path
                output_path.parent.mkdir(parents=True, exist_ok=True)

            # 保存图像（使用高质量）
            cv2.imwrite(str(output_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])

            self.logger.log("camera", "info", f"捕获图像: {output_path}")

            # 返回相对于项目根目录的路径（用于数据库存储和 Web 访问）
            relative_path = output_path.relative_to(self.project_root)
            return str(relative_path)

        except Exception as e:
            self.logger.log("camera", "error", f"捕获图像失败: {e}")
            return None

    def read_frame(self) -> Optional[tuple]:
        """读取一帧（用于视频流）

        注意：不需要锁，因为：
        1. 只有视频流生成器在调用（单线程）
        2. cap.read() 本身是线程安全的（OpenCV 内部有锁）

        Returns:
            (ret, frame) 元组，失败返回 None
        """
        if self.cap is None or not self.cap.isOpened():
            return None

        try:
            ret, frame = self.cap.read()
            if ret:
                self.last_frame = frame
                self.last_frame_time = time.time()
            return ret, frame
        except Exception as e:
            self.logger.log("camera", "error", f"读取帧失败: {e}")
            return None

    def shutdown(self):
        """关闭摄像头"""
        with self.mode_lock:
            if self.cap:
                self.cap.release()
                self.cap = None
            self.mode = None
            self.logger.log("camera", "info", "摄像头已关闭")


# 全局单例实例
_camera_singleton: Optional[CameraSingleton] = None
_singleton_lock = threading.Lock()


def get_camera_singleton(config: Config) -> CameraSingleton:
    """获取摄像头单例实例"""
    global _camera_singleton
    if _camera_singleton is None:
        with _singleton_lock:
            if _camera_singleton is None:
                _camera_singleton = CameraSingleton(config)
    return _camera_singleton
