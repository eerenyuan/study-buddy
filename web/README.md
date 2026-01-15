# Study Buddy System - Web Interface

Web interface and API for the Study Buddy System.

## 功能特性

### 🎯 核心功能
- **实时监控**: 定时截图，AI 分析学习状态
- **启动预览**: 启动监控时自动播放摄像头画面（用于调试）
- **智能通知**: 连续失败达到阈值时发送提醒
- **规则配置**: 灵活的自定义规则（正则表达式）
- **时间调度**: 支持每日自动启停
- **Web 管理**: 完整的 Web 界面和 RESTful API

### 📱 支持平台
- 企业微信
- Telegram（可扩展）

## 快速开始

### 1. 安装依赖

```bash
pip install flask python-dotenv
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并配置：

```env
# Kimi API 配置
KIMI_API_KEY=your_api_key_here

# 企业微信配置（可选）
WECHAT_CORPID=your_corpid
WECHAT_SECRET=your_secret
WECHAT_AGENTID=your_agentid
WECHAT_TOUSER=user1|user2

# Telegram 配置（可选）
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 3. 启动 Web 服务

```bash
python run_web.py
```

访问地址：
- 主页: http://localhost:5000
- 配置: http://localhost:5000/config
- 记录: http://localhost:5000/records

## API 接口

### 获取系统状态
```
GET /api/status
```

### 获取配置
```
GET /api/config
```

### 更新配置
```
POST /api/config
Content-Type: application/json

{
  "rules": [
    {"key": "at_desk", "regexp": "^true$"},
    {"key": "is_study", "regexp": "^true$"}
  ],
  "min_notify_interval": 10,
  "max_notify_interval": 60,
  "consecutive_fail_limit": 5,
  "capture_interval": 30
}
```

### 启动监控
```
POST /api/monitor/start
```

### 停止监控
```
POST /api/monitor/stop
```

### 获取今天的记录
```
GET /api/records/today
```

### 获取最近的记录
```
GET /api/records/recent
```

## 配置说明

### 规则配置

规则使用 key + regexp 格式：

```json
{
  "rules": [
    {"key": "at_desk", "regexp": "^true$"},
    {"key": "is_study", "regexp": "^true$"},
    {"key": "activity", "regexp": "^(看书|写字)$"},
    {"key": "posture", "regexp": "^(端正)$"},
    {"key": "lighting", "regexp": "^(充足|一般)$"}
  ]
}
```

### 通知参数

- **min_notify_interval**: 最小通知间隔（分钟）
  - 如果距离上次通知时间太短，不通知（即使不合格）

- **max_notify_interval**: 最大通知间隔（分钟）
  - 如果距离上次通知时间太久，强制通知（即使合格）

- **consecutive_fail_limit**: 连续失败限制
  - 连续失败达到此次数后，自动停止服务

### 监控参数

- **capture_interval**: 截图间隔（秒）
- **preview_duration**: 预览时长（秒）
- **enable_preview**: 是否启用预览

### 时间调度

- **auto_start_time**: 自动开始时间（HH:MM 格式）
- **auto_stop_time**: 自动停止时间（HH:MM 格式）
- **enable_time_scheduler**: 是否启用时间调度

## 项目结构

```
web_v2/
├── app.py              # Flask 应用
├── templates/          # HTML 模板
│   ├── index.html      # 主页
│   ├── config.html     # 配置页面
│   └── records.html    # 记录页面
└── static/             # 静态文件
    ├── css/
    │   └── style.css
    └── js/
        ├── main.js      # 主页脚本
        ├── config.js   # 配置脚本
        └── records.js  # 记录脚本
```

## 技术栈

- **后端**: Flask + Python 3.8+
- **前端**: HTML + CSS + JavaScript
- **AI**: Kimi Vision API
- **存储**: SQLite
- **消息**: 企业微信 / Telegram

## 使用流程

1. **配置规则**: 在配置页面设置自定义规则
2. **启动监控**: 点击"启动监控"按钮
   - 系统会自动显示摄像头预览画面（用于调试）
   - 预览持续 `preview_duration` 秒后自动关闭
   - 预览结束后，监控程序开始正常截图检测
3. **查看记录**: 在记录页面查看历史检测记录

## API 接口

### 获取系统状态
```
GET /api/status
```

### 获取预览状态
```
GET /api/preview/status
```
返回：
```json
{
  "success": true,
  "active": true,
  "remaining": 8.5
}
```

### 视频流端点（仅预览阶段可用）
```
GET /video_feed
```
返回 MJPEG 视频流，仅在预览阶段可用

## 注意事项

- Web 服务需要摄像头访问权限
- 确保 .env 文件中配置了正确的 API Key
- 首次运行会自动创建配置文件 `config/monitor_config.json`
- 所有配置修改会自动保存到文件
- 预览视频流仅在启动监控后的 `preview_duration` 秒内可用
- 预览结束后摄像头会自动释放，监控程序开始正常截图
