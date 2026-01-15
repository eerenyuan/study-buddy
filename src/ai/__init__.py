"""
AI 模块 - 统一的 AI 功能入口

架构：
┌─────────────────────────────────────┐
│          AIService (统一入口)        │
├─────────────────────────────────────┤
│  vision() → VisionAnalyzer          │  ← 图像分析
│  chat() → ChatAnalyzer (未来)        │  ← 聊天
│  solve() → Solver (未来)             │  ← 解题
├─────────────────────────────────────┤
│  AIConfig (配置层)                   │  ← API Key, 模型配置
└─────────────────────────────────────┘

使用示例：
```python
from src.ai import create_ai_service, AIConfig

# 1. 创建配置
config = AIConfig(
    api_key="your_api_key",
    model="moonshot-v1-8k",
    vision_model="moonshot-vision"
)

# 2. 创建 AI 服务
ai = create_ai_service(config)

# 3. 使用 Vision 分析
vision = ai.vision()
analysis = vision.analyze("/path/to/image.jpg")
print(analysis)
# {
#   "is_desk_present": false,
#   "is_posture_correct": false,
#   "is_away": true,
#   "confidence": 0.95
# }

# 4. 未来：使用聊天
# chat = ai.chat()
# response = chat.chat("帮我查资料")

# 5. 未来：使用解题
# solver = ai.solve()
# solution = solver.solve("这道数学题...")
```
"""

from .ai_config import AIConfig
from .ai_service import AIService, create_ai_service
from .vision_analyzer import VisionAnalyzer

__all__ = [
    # 配置
    'AIConfig',

    # 服务
    'AIService',
    'create_ai_service',

    # 分析器
    'VisionAnalyzer',
]
