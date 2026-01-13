"""
Vision 模块 - 负责图像捕获和分析
"""
from pathlib import Path
from typing import Dict, Any
import base64
import time
import httpx
from PIL import Image

from core.base import BaseModule, Analyzer, Logger
from core.config import Config


class Camera(BaseModule):
    """摄像头管理类"""

    def __init__(self, config: Config):
        super().__init__(config)
        self.logger = Logger(config.log_dir)
        self.cap = None

    def initialize(self) -> bool:
        """初始化摄像头"""
        try:
            import cv2

            # 尝试使用配置的索引
            self.cap = cv2.VideoCapture(self.config.camera.camera_index)

            if not self.cap.isOpened():
                self.logger.log("camera", "error", f"无法打开摄像头 (索引: {self.config.camera.camera_index})")
                self.logger.log("camera", "warning", "尝试自动检测可用摄像头...")

                # 自动检测可用摄像头（尝试索引0-5）
                for idx in range(6):
                    test_cap = cv2.VideoCapture(idx)
                    if test_cap.isOpened():
                        test_cap.release()
                        self.logger.log("camera", "info", f"检测到可用摄像头: 索引 {idx}")
                        self.cap = cv2.VideoCapture(idx)
                        if self.cap.isOpened():
                            self.config.camera.camera_index = idx  # 更新配置
                            break

                # 再次检查
                if not self.cap.isOpened():
                    self.logger.log("camera", "error", "未找到可用的摄像头")
                    return False

            # 设置分辨率
            width, height = self.config.camera.resolution
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            # 尝试设置缓冲区大小为1（如果摄像头支持）
            # 这样可以最大限度地减少滞后
            try:
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                buffer_size = self.cap.get(cv2.CAP_PROP_BUFFERSIZE)
                self.logger.log("camera", "info", f"缓冲区大小设置为: {buffer_size}")
            except:
                self.logger.log("camera", "warning", "无法设置缓冲区大小（摄像头可能不支持）")

            self.logger.log("camera", "info", f"摄像头初始化成功 - 索引: {self.config.camera.camera_index}, 分辨率: {width}x{height}")
            return True

        except ImportError:
            self.logger.log("camera", "warning", "OpenCV 未安装，无法使用摄像头功能")
            self.logger.log("camera", "info", "安装方法: pip install opencv-python")
            return False
        except Exception as e:
            self.logger.log("camera", "error", f"摄像头初始化失败: {e}")
            return False

    def shutdown(self):
        """关闭摄像头"""
        if self.cap:
            self.cap.release()
            self.cap = None
        self.logger.log("camera", "info", "摄像头已关闭")

    def reinitialize(self) -> bool:
        """重新初始化摄像头（用于恢复连接）"""
        self.logger.log("camera", "warning", "尝试重新初始化摄像头...")
        self.shutdown()
        time.sleep(1)  # 等待1秒让资源释放
        return self.initialize()

    def capture(self, output_path: str = None) -> str:
        """捕获图像

        Args:
            output_path: 输出文件路径，如果不指定则使用临时文件

        Returns:
            图片文件路径
        """
        if not self.cap:
            # 如果摄像头未初始化，尝试使用测试图片
            if output_path and Path(output_path).exists():
                self.logger.log("camera", "info", f"使用测试图片: {output_path}")
                return output_path
            raise NotImplementedError("摄像头未初始化，请先安装 opencv-python 并确保摄像头可用")

        try:
            import cv2
            import time

            # 重试机制：最多尝试3次
            max_retries = 3
            for attempt in range(max_retries):
                # 清空缓冲区：读取并丢弃2帧以获取最新画面
                for _ in range(2):
                    self.cap.read()

                # 读取最新的帧
                ret, frame = self.cap.read()
                if ret:
                    # 成功读取，退出重试循环
                    break

                # 读取失败，如果是最后一次尝试，抛出异常
                if attempt == max_retries - 1:
                    raise Exception(f"无法从摄像头读取图像（已重试{max_retries}次）")

                # 等待一小段时间后重试
                self.logger.log("camera", "warning", f"第{attempt + 1}次读取失败，等待0.5秒后重试...")
                time.sleep(0.5)

            # 如果未指定输出路径，使用临时文件
            if not output_path:
                output_path = f"temp_capture_{int(time.time())}.jpg"

            # 保存图像
            cv2.imwrite(output_path, frame,
                        [int(cv2.IMWRITE_JPEG_QUALITY), self.config.camera.quality])

            self.logger.log("camera", "info", f"捕获图像到: {output_path}")
            return output_path

        except Exception as e:
            self.logger.log("camera", "error", f"捕获图像失败: {e}")
            raise


class KimiVisionAnalyzer(BaseModule, Analyzer):
    """Kimi Vision 分析器"""

    PROMPT = """你是学习监督助手，分析图片中孩子的学习状态。

返回JSON格式：
{
  "at_desk": true/false,
  "is_playing": true/false,
  "activity": "看书/写字/用电脑/玩手机/发呆/其他",
  "is_study_related": true/false/unknown,
  "content_description": "简短描述看的内容",
  "posture": "端正/不佳/趴着/歪坐/其他",
  "lamp_on": true/false,
  "lighting": "充足/一般/昏暗",
  "overall_status": "当前学习状态的完整描述（20-100字）",
  "suggestion": "简短建议（10字以内）"
}

只返回纯JSON，无其他内容。"""

    def __init__(self, config: Config):
        super().__init__(config)
        self.logger = Logger(config.log_dir)

    def initialize(self) -> bool:
        """初始化分析器"""
        self.logger.log("vision", "info", f"Kimi Vision 初始化 - 模型: {self.config.kimi.model}")
        return True

    def shutdown(self):
        """关闭分析器"""
        self.logger.log("vision", "info", "Kimi Vision 已关闭")

    def analyze(self, image_path: str) -> Dict[str, Any]:
        """分析图像

        Args:
            image_path: 图片路径

        Returns:
            分析结果
        """
        self.logger.log("vision", "info", f"开始分析: {image_path}")

        # 预处理图片
        processed_path = self._preprocess_image(image_path)

        # 调用 Kimi API
        result = self._call_kimi_api(processed_path)

        # 清理临时文件
        if processed_path != image_path and Path(processed_path).exists():
            Path(processed_path).unlink()

        return result

    def _preprocess_image(self, image_path: str) -> str:
        """预处理图片（调整分辨率）

        Args:
            image_path: 原始图片路径

        Returns:
            处理后的图片路径
        """
        img = Image.open(image_path)
        width, height = img.size
        target_width, target_height = self.config.camera.resolution

        # 如果图片已经小于等于目标尺寸，不需要调整
        if width <= target_width and height <= target_height:
            return image_path

        # 调整图片大小（保持宽高比）
        img.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)

        # 保存到临时文件
        temp_path = Path(image_path).stem + "_processed.jpg"
        img.save(temp_path, "JPEG", quality=self.config.camera.quality)

        self.logger.log("vision", "info", f"图片调整: {width}x{height} -> {img.size}")

        return temp_path

    def _call_kimi_api(self, image_path: str) -> Dict[str, Any]:
        """调用 Kimi Vision API

        Args:
            image_path: 图片路径

        Returns:
            API 响应结果
        """
        # 编码图片
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        # 构建 API 请求
        start_time = time.time()

        response = httpx.post(
            f"{self.config.kimi.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.config.kimi.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.config.kimi.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
                            }
                        ]
                    }
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            },
            timeout=self.config.kimi.timeout
        )

        elapsed = time.time() - start_time

        if response.status_code == 200:
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "{}")

            # 解析 JSON
            import json
            try:
                parsed = json.loads(content)
                self.logger.log("vision", "info", f"分析完成 (耗时: {elapsed:.2f}s)")
                return parsed
            except json.JSONDecodeError as e:
                self.logger.log("vision", "error", f"JSON 解析失败: {e}")
                return {"error": "JSON 解析失败", "raw_content": content}
        else:
            error_msg = response.text
            self.logger.log("vision", "error", f"API 调用失败: {error_msg}")
            return {"error": "API 调用失败", "status_code": response.status_code}


def create_vision_module(config: Config):
    """创建 Vision 模块工厂函数"""
    return {
        "camera": Camera(config),
        "analyzer": KimiVisionAnalyzer(config)
    }
