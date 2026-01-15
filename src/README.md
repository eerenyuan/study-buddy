# 重构后的模块

## 文件结构

```
modules_refactored/
├── vision/                    # Vision 模块（硬件层）✅
│   ├── __init__.py
│   ├── camera_singleton.py   # 单例摄像头管理类
│   └── camera_service.py     # 摄像头服务类（capture/preview）
│
├── messenger/                # Messenger 模块（消息服务）✅
│   ├── __init__.py
│   ├── messenger_service.py  # 消息服务类
│   ├── adapters/             # 适配器层
│   │   ├── __init__.py
│   │   ├── base_adapter.py   # 基类适配器
│   │   ├── wechat_adapter.py # 企业微信适配器
│   │   └── telegram_adapter.py # Telegram 适配器
│   └── models/               # 数据模型
│       ├── __init__.py
│       └── message.py        # 消息模型（支持双向）
│
├── monitor/                  # Monitor 模块（监控服务）✅
│   ├── __init__.py
│   ├── monitor_service.py    # 监控服务类
│   ├── monitor_config.py     # 监控配置类
│   └── decision_engine.py    # 决策引擎
│
├── ai/                       # AI 模块（AI 服务）✅
│   ├── __init__.py
│   ├── ai_service.py         # 统一的 AI 服务入口
│   ├── ai_config.py          # AI 配置类
│   └── vision_analyzer.py    # Vision 分析器
│
└── storage/                  # Storage 模块（存储服务）✅
    ├── __init__.py
    └── detection_record_service.py  # 检测记录存储（SQLite）
```

## 已完成重构的模块

### 1. Vision 模块 ✅

**架构**：
- 硬件层：CameraSingleton（单例摄像头）
- 配置层：CameraServiceConfig（显式依赖）
- 业务层：CameraService（监控+预览）

**关键特性**：
- 单例模式：全局只有一个摄像头实例
- 两种模式：monitor（监控）、preview（预览）
- 模式互斥：自动切换，带延迟处理
- 客户端协商：预览模式支持多客户端竞争

### 2. Messenger 模块 ✅

**架构**：
```
┌─────────────────────────────────────┐
│     MessengerService (业务层)       │
├─────────────────────────────────────┤
│     MessengerConfig (配置层)        │
├─────────────────────────────────────┤
│     MessageAdapter (适配器层)       │
│     - WeChatAdapter                 │
│     - TelegramAdapter                │
├─────────────────────────────────────┤
│     Message (数据模型层)             │
└─────────────────────────────────────┘
```

**关键特性**：
- 适配器模式：统一接口，支持多平台
- 消息模型：支持双向沟通（已预留接口）
- 多平台广播：一条消息发送到所有平台
- 显式依赖注入：使用配置对象

**支持的消息类型**：
- 文本消息
- Markdown 消息
- 图片消息
- 卡片消息

**未来扩展**：
- 接收消息（通过回调接口）
- 交互按钮（卡片消息的按钮）
- 会话管理

### 3. Monitor 模块 ✅

**架构**：
```
┌─────────────────────────────────────────────────┐
│     MonitorService (监控服务)                    │
├─────────────────────────────────────────────────┤
│  核心业务流程：                                  │
│  - process_snapshot(image_path)                 │
│    → AI 分析 → 决策 → 存储 → 通知                │
│                                                 │
│  监控循环管理：                                  │
│  - start_monitor() / stop_monitor()             │
│    → 先预览（可选），再监控循环                   │
│                                                 │
│  时间调度管理：                                  │
│  - start_time_scheduler() / stop_time_scheduler()│
│    → 定时启动/停止监控                            │
├─────────────────────────────────────────────────┤
│  DecisionEngine (决策引擎)                       │
│  - 单张照片检查（与时间无关）                     │
│  - 时间维度判断（频率控制、防抖动）               │
├─────────────────────────────────────────────────┤
│  MonitorConfig (配置层)                          │
│  - capture_interval / preview_duration          │
│  - notify_interval_minutes / alert_threshold     │
│  - auto_start_time / auto_stop_time             │
└─────────────────────────────────────────────────┘
```

**关键特性**：
- **流程控制**：预览 → 监控循环（自动切换）
- **智能决策**：连续失败阈值 + 通知间隔（防抖动）
- **定时调度**：支持自动启动/停止监控
- **完整记录**：每次检测都保存完整信息
- **显式依赖注入**：所有依赖通过构造函数传入

### 4. AI 模块 ✅

**架构**：
```
┌─────────────────────────────────────┐
│     AIService (统一入口)            │
├─────────────────────────────────────┤
│  vision() → VisionAnalyzer          │  ← 图像分析
│  chat() → ChatAnalyzer (未来)        │  ← 聊天
│  solve() → Solver (未来)             │  ← 解题
├─────────────────────────────────────┤
│  AIConfig (配置层)                   │
│  - api_key / model / provider        │
└─────────────────────────────────────┘
```

**关键特性**：
- **统一管理**：所有 AI 功能集中在一个模块
- **配置共享**：API Key、模型配置统一管理
- **易于扩展**：添加新功能只需添加新方法
- **Vision 分析**：基于 Kimi Vision API

### 5. Storage 模块 ✅

**架构**：
```
DetectionRecordService (检测记录存储)
├── save()           # 保存检测记录
├── get_today()      # 查询今天的记录
└── get_status()     # 获取存储状态

存储方式：SQLite 数据库
数据字段：
- timestamp       # 时间戳
- image_path      # 图片路径
- is_valid        # 是否合格
- issues          # 问题列表（JSON）
- should_notify   # 是否通知
- analysis_json   # 完整 AI 分析结果（JSON）
```

**关键特性**：
- **轻量级**：SQLite，无需额外服务
- **完整记录**：保存完整的 AI 分析 JSON
- **简洁 API**：只实现必要功能
- **易于扩展**：未来可添加统计功能

## 待重构的模块

无！所有核心模块已完成重构 ✅

## 重构原则

1. **显式依赖注入**：通过配置对象注入依赖
2. **分层架构**：Web → Service → Adapter/Module
3. **单一职责**：每个类只负责一件事
4. **适配器模式**：统一接口，易于扩展
5. **开放封闭**：对扩展开放，对修改封闭

## 使用示例

### Camera 模块
```python
from modules_refactored.vision import get_camera_service, CameraServiceConfig

# 创建配置
config = CameraServiceConfig(
    preview_timeout=300,
    log_dir="logs"
)

# 获取服务
camera = get_camera_service(camera_singleton, config)

# 使用
image_path = camera.capture()  # 单次截图
camera.start_preview("client_123")  # 启动预览
camera.stop_preview("client_123")  # 停止预览
```

### Messenger 模块
```python
from modules_refactored.messenger import create_messenger_service, MessengerConfig

# 创建配置
config = MessengerConfig(
    wechat_corpid="...",
    wechat_secret="...",
    wechat_agentid="...",
    wechat_recipient="user1|user2"
)

# 创建服务
messenger = create_messenger_service(config)

# 使用
messenger.send("监控已启动", MessageLevel.INFO)
messenger.send_image("/path/to/image.jpg")
```

### Monitor 模块
```python
from modules_refactored.monitor import create_monitor_service, MonitorConfig

# 创建配置
config = MonitorConfig(
    capture_interval=30,                   # 每 30 秒截图一次
    notify_interval_minutes=10,            # 通知间隔 10 分钟
    alert_threshold=3,                     # 连续 3 次失败才通知
    preview_duration=10,                   # 先预览 10 秒
    enable_preview=True,                   # 启用预览
    auto_start_time="09:00",               # 每天 9 点自动启动
    auto_stop_time="18:00"                 # 每天 6 点自动停止
)

# 创建服务（需要先创建 AI、Messenger、Camera、Storage 服务）
monitor = create_monitor_service(
    ai_service=ai,
    messenger_service=messenger,
    camera_service=camera,
    storage_service=storage,
    config=config
)

# 使用
monitor.start_monitor()           # 启动监控（会先预览再监控）
monitor.start_time_scheduler()    # 启动时间调度（可选）
status = monitor.get_status()     # 查询状态
```

### AI 模块
```python
from modules_refactored.ai import create_ai_service, AIConfig

# 创建配置
config = AIConfig(
    api_key="your_api_key",
    model="moonshot-v1-8k",
    vision_model="moonshot-vision"
)

# 创建服务
ai = create_ai_service(config)

# 使用 Vision 分析
vision = ai.vision()
analysis = vision.analyze("/path/to/image.jpg")
print(analysis)
# {
#   "is_desk_present": false,
#   "is_posture_correct": false,
#   "is_away": true,
#   "confidence": 0.95
# }
```

### Storage 模块
```python
from modules_refactored.storage import get_detection_record_service

# 创建服务
storage = get_detection_record_service(db_path="data/detection_records.db")

# 保存检测记录
storage.save(
    image_path="/path/to/image.jpg",
    is_valid=False,
    issues=["不在桌前", "坐姿不正确"],
    should_notify=True,
    analysis={"is_desk_present": False, ...}  # 完整的 AI 分析结果
)

# 查询今天的记录
today_records = storage.get_today()
for record in today_records:
    print(f"{record['timestamp']}: {record['is_valid']} - {record['issues']}")
```

---

## 架构总结

所有核心模块已完成重构！✅

| 模块 | 职责 | 关键类 |
|------|------|--------|
| **Vision** | 摄像头硬件管理 | CameraService (capture/preview) |
| **Messenger** | 消息通知 | MessengerService + 适配器 |
| **Monitor** | 监控业务协调 | MonitorService + DecisionEngine |
| **AI** | AI 分析服务 | AIService → VisionAnalyzer |
| **Storage** | 检测记录存储 | DetectionRecordService (SQLite) |

**设计原则**：
- ✅ 显式依赖注入：所有配置通过配置对象传入
- ✅ 分层架构：Web → Service → Adapter/Module
- ✅ 单一职责：每个类只负责一件事
- ✅ 适配器模式：统一接口，易于扩展
- ✅ 开放封闭：对扩展开放，对修改封闭

