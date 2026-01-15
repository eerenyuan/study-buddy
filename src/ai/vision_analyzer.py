"""
Vision 分析器

基于 Kimi Vision API 的图像分析
"""
import base64
from pathlib import Path
from typing import Dict, Any, Optional
import time

import httpx

from src.common import Logger


class VisionAnalyzer:
    """Vision 分析器

    职责：
    1. 封装 Kimi Vision API 调用
    2. 处理图片编码（base64）
    3. 解析 JSON 响应

    设计原则：
    - 单一职责：只负责图像分析
    - 无状态：不保存分析历史
    - 可重试：支持自动重试
    """

    def __init__(self, api_key: str, base_url: str, model: str,
                 timeout: int = 30, max_retries: int = 3,
                 log_dir: str = "logs", project_root: Optional[Path] = None):
        """
        Args:
            api_key: Kimi API Key
            base_url: API 基础 URL
            model: 模型名称
            timeout: 请求超时（秒）
            max_retries: 最大重试次数
            log_dir: 日志目录
            project_root: 项目根目录（用于解析相对路径）
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = Logger(log_dir)
        self.project_root = project_root or Path(__file__).parent.parent.parent

    def analyze(self, image_path: str) -> Dict[str, Any]:
        """分析图片

        Args:
            image_path: 图片路径

        Returns:
            AI 分析结果（JSON 格式），例如：
            {
                "is_desk_present": false,
                "is_posture_correct": false,
                "is_playing": false,
                "is_away": true,
                "confidence": 0.95,
                "description": "学生不在书桌前"
            }

        Raises:
            Exception: 分析失败时抛出异常
        """
        self.logger.log("ai", "info", f"开始分析图片: {image_path}")

        # 1. 编码图片
        image_base64 = self._encode_image(image_path)
        if not image_base64:
            raise Exception(f"图片编码失败: {image_path}")

        # 2. 构建 Prompt
        prompt = self._build_prompt()

        # 3. 调用 API（带重试）
        response_json = self._call_api_with_retry(prompt, image_base64)

        # 4. 解析响应
        analysis = self._parse_response(response_json)

        self.logger.log("ai", "info", f"分析完成: {analysis}")
        return analysis

    def _encode_image(self, image_path: str) -> Optional[str]:
        """将图片编码为 base64

        Args:
            image_path: 图片路径

        Returns:
            base64 编码的字符串，失败返回 None
        """
        try:
            # 将相对路径转换为绝对路径
            path = Path(image_path)
            if not path.is_absolute():
                path = self.project_root / image_path

            if not path.exists():
                self.logger.log("ai", "error", f"图片不存在: {image_path} (尝试: {path})")
                return None

            with open(path, "rb") as f:
                image_data = f.read()
                image_base64 = base64.b64encode(image_data).decode("utf-8")

            self.logger.log("ai", "info", f"图片编码成功: {len(image_base64)} 字符")
            return image_base64

        except Exception as e:
            self.logger.log("ai", "error", f"图片编码异常: {e}")
            return None

    def _build_prompt(self) -> str:
        """构建分析 Prompt

        Returns:
            Prompt 字符串
        """
        return """
        你是学习监督助手，分析图片中孩子的学习状态。

返回JSON格式：
{
  "at_desk": true/false, #孩子是否坐在书桌前
  "is_study": true/false,  #是否在学习
  "activity": "看书/写字/用电脑/玩手机/发呆/其他",
  "posture": "端正/不佳/趴着/歪坐/其他", #请特别关注学生的【下肢和脚部姿势】，判断是否存在不规范坐姿， 例如：脚踩在椅子上、双腿蜷缩在椅面、盘腿坐在椅子上等。
  "lighting": "充足/一般/昏暗",
  "overall_status": "当前学习状态的完整描述（20-100字）"
}

只返回纯JSON，无其他内容。
        """
#         """请分析这张图片，判断学生当前是否认真坐在书桌前学习。

# 你需要基于【可见的视觉信息】进行判断。
# 如果某一项无法从图片中明确判断，请返回 false，并在 description 中说明“不确定”。

# 请仅返回一个合法的 JSON 对象，不要输出任何多余文字。

# 返回格式如下：

# {
#   "is_desk_present": true/false,        // 学生是否明显坐在书桌或学习桌前（有桌面且人与桌距离合理）
#   "is_posture_correct": true/false,     // 坐姿是否相对端正（非趴桌、歪躺、趴床等）
#   "is_facing_desk": true/false,         // 身体和头部是否大致朝向桌面/学习区域
#   "is_study": true/false,               // 是否正在进行学习相关活动（如看书、写字、使用电脑/平板学习）
#   "is_distracted": true/false,          // 是否存在明显分心行为（如玩手机、看无关视频、东张西望）
#   "is_light_ok": true/false,             // 光线是否充足且适合阅读/书写（非明显昏暗或强烈逆光）
#   "desk_is_orderly": true/false,         // 桌面是否以学习用品为主（书本、作业、文具等），而非明显娱乐物品
#   "overall_focus_level": "high|medium|low", // 综合判断的专注程度
#   "description": "对学生学习状态的简要客观描述，不要做道德评价"
# }
# """

    def _call_api_with_retry(self, prompt: str, image_base64: str) -> Dict[str, Any]:
        """调用 API（带重试）

        Args:
            prompt: 提示词
            image_base64: base64 编码的图片

        Returns:
            API 响应的 JSON

        Raises:
            Exception: 重试失败后抛出异常
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                return self._call_api(prompt, image_base64)

            except Exception as e:
                last_error = e
                self.logger.log("ai", "warning",
                               f"API 调用失败（第 {attempt + 1} 次）: {e}")

                if attempt < self.max_retries - 1:
                    # 等待后重试
                    time.sleep(1)

        # 所有重试都失败
        raise Exception(f"API 调用失败（已重试 {self.max_retries} 次）: {last_error}")

    def _call_api(self, prompt: str, image_base64: str) -> Dict[str, Any]:
        """调用 Kimi Vision API

        Args:
            prompt: 提示词
            image_base64: base64 编码的图片

        Returns:
            API 响应的 JSON

        Raises:
            Exception: API 调用失败时抛出异常
        """
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            "temperature": 0.3,  # 降低随机性，提高稳定性
            "response_format": {"type": "json_object"}  # 启用 JSON 模式，确保返回有效 JSON
        }

        response = httpx.post(url, json=data, headers=headers, timeout=self.timeout)
        response.raise_for_status()

        response_json = response.json()

        # 提取 AI 返回的内容
        if "choices" in response_json and len(response_json["choices"]) > 0:
            content = response_json["choices"][0]["message"]["content"]
            return {"raw_content": content}

        raise Exception(f"API 响应格式错误: {response_json}")

    def _parse_response(self, response_json: Dict[str, Any]) -> Dict[str, Any]:
        """解析 API 响应

        Args:
            response_json: API 响应的 JSON

        Returns:
            解析后的分析结果
        """
        import json

        raw_content = response_json.get("raw_content", "")

        try:
            # 尝试直接解析 JSON
            analysis = json.loads(raw_content)
            return analysis

        except json.JSONDecodeError:
            
            # 返回默认值
            self.logger.log("ai", "warning", f"无法解析 JSON，使用默认值: {raw_content[:100]}")
            return {
                "is_desk_present": True,
                "is_posture_correct": True,
                "is_playing": False,
                "is_away": False,
                "confidence": 0.5,
                "description": "无法解析 AI 响应"
            }

    def test_connection(self) -> bool:
        """测试 API 连接

        Returns:
            是否连接成功
        """
        try:
            # 发送一个简单的请求测试连接
            url = f"{self.base_url}/chat/completions"

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            data = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": "Hello"
                    }
                ],
                "max_tokens": 10
            }

            response = httpx.post(url, json=data, headers=headers, timeout=self.timeout)
            response.raise_for_status()

            self.logger.log("ai", "info", "API 连接测试成功")
            return True

        except Exception as e:
            self.logger.log("ai", "error", f"API 连接测试失败: {e}")
            return False
