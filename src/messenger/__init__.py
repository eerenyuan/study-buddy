"""
Messenger 模块 - 消息传递服务

架构：显式依赖注入，支持双向沟通（扩展中）

分层架构：
┌─────────────────────────────────────┐
│     Web Layer (Flask Routes)        │  ← HTTP 请求处理
├─────────────────────────────────────┤
│     MessengerService (业务层)       │  ← 业务逻辑协调
│     - send()                        │
│     - broadcast()                   │
│     - start_receiving()             │
├─────────────────────────────────────┤
│     MessengerConfig (配置层)        │  ← 显式依赖注入
│     - platform configs              │
│     - default_recipient             │
├─────────────────────────────────────┤
│     MessageAdapter (适配器层)       │  ← 平台实现
│     - WeChatAdapter                │
│     - TelegramAdapter               │
├─────────────────────────────────────┤
│     Message (数据模型层)             │  ← 消息模型
│     - MessageDirection              │
│     - MessageType                   │
│     - SendMessageRequest            │
└─────────────────────────────────────┘

使用示例：
```python
# 1. 创建配置
config = MessengerConfig(
    wechat_corpid="...",
    wechat_secret="...",
    wechat_agentid="...",
    wechat_recipient="user1|user2"
)

# 2. 创建服务
service = create_messenger_service(config)

# 3. 发送消息
service.send("监控已启动", MessageLevel.INFO)

# 4. 发送图片
service.send_image("/path/to/image.jpg")

# 5. 未来：接收消息
service.start_receiving(on_message_callback)
```
"""

from .models import (
    MessageDirection,
    MessageType,
    MessageLevel,
    Message
)

from .adapters import (
    MessageAdapter,
    WeChatAdapter,
    TelegramAdapter
)

from .messenger_service import (
    MessengerService,
    MessengerConfig,
    create_messenger_service
)

__all__ = [
    # 数据模型
    'MessageDirection',
    'MessageType',
    'MessageLevel',
    'Message',

    # 适配器
    'MessageAdapter',
    'WeChatAdapter',
    'TelegramAdapter',

    # 服务
    'MessengerService',
    'MessengerConfig',
    'create_messenger_service',
]
