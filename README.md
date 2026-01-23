# Study Buddy - AI 学习伙伴

<div align="center">

基于 AI 视觉的智能学习陪伴系统，通过摄像头实时分析学习状态，并通过 Web 界面提供友好的规则配置和监控管理。

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README_EN.md) | 简体中文

</div>

---

## ✨ 主要功能

- 🎯 **智能分析**: 使用 Kimi Vision API 分析学习状态
- 📸 **实时监控**: 自动捕获学习场景照片，支持可配置的截图间隔
- 💬 **智能通知**: 支持企业微信多收件人通知，智能通知间隔控制
- 🖥️ **Web 管理**: 可视化配置规则和监控界面，实时状态查看
- ⚙️ **灵活规则**: Web 页面自定义提醒规则（正则表达式）
- 📊 **历史记录**: 完整的学习状态历史，不合格红色标记
- ⏰ **定时任务**: 每天自动启动和停止监控
- 🎥 **实时预览**: 启动时短暂预览摄像头画面，确保位置正确
- 🛡️ **智能保护**: 连续失败达到限制自动停止监控

## 📁 项目结构

```
study-buddy/
├── src/                    # 核心业务逻辑
│   ├── ai/                # AI 分析模块
│   │   └── vision_analyzer.py
│   ├── messenger/         # 消息通知模块
│   │   ├── adapters/      # 企业微信/Telegram 适配器
│   │   └── messenger_service.py
│   ├── monitor/           # 监控服务模块
│   │   ├── simple_monitor_service.py
│   │   ├── notify_manager.py
│   │   └── simple_rule_checker.py
│   ├── storage/           # 存储模块
│   │   └── detection_storage.py
│   ├── vision/            # 摄像头模块
│   │   ├── camera_service.py
│   │   └── camera_singleton.py
│   └── common.py          # 通用工具类
├── web/                   # Web 界面
│   ├── app.py             # Flask 应用入口
│   ├── static/            # CSS, JS, 静态资源
│   └── templates/         # HTML 模板
├── config/                # 配置文件
│   └── monitor_config.json
├── data/                  # 运行时数据（会被 Git 忽略）
│   ├── captures/          # 捕获的图片
│   └── detection_records.db
├── logs/                  # 日志文件（会被 Git 忽略）
├── .env                   # 环境变量（需要创建，见 .env.example）
├── requirements.txt       # Python 依赖
├── README.md              # 中文说明
└── README_EN.md           # 英文说明
```

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/eerenyuan/study-buddy.git
cd study-buddy
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

**主要依赖**：
- Python 3.8+
- Flask 2.0+
- OpenCV (cv2)
- Requests

### 3. 配置环境变量

复制 `.env.example` 为 `.env` 并填入配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入必要的配置：

```env
# Kimi Vision API 配置
KIMI_API_KEY=your_kimi_api_key_here

# 企业微信配置
WECHAT_CORPID=your_corp_id
WECHAT_AGENTID=your_agent_id
WECHAT_SECRET=your_app_secret
WECHAT_TOUSER=RenYuan|xiaoyu

# Telegram 配置（可选）
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

### 4. 启动应用

```bash
cd web
python app.py
```

访问 http://localhost:5000

## 📝 使用说明

### 首次使用流程

1. **启动应用**：`cd web && python app.py`
2. **访问配置页面**：http://localhost:5000/config
3. **配置监控规则**：
   - 添加规则字段（如：`at_desk`, `is_study`, `activity`, `posture`, `lighting`）
   - 设置正则表达式（如：`^true$` 表示必须完全匹配 "true"）
   - 配置通知间隔和失败限制
4. **配置收件人**：http://localhost:5000/messenger_test
5. **启动监控**：在首页点击"启动监控"

### 监控规则示例

```json
{
  "rules": [
    {"key": "at_desk", "regexp": "^true$"},
    {"key": "is_study", "regexp": "^true$"},
    {"key": "activity", "regexp": "^(看书)$"},
    {"key": "posture", "regexp": "^(端正)$"},
    {"key": "lighting", "regexp": "^(充足)$"}
  ]
}
```

**规则说明**：
- `at_desk`: 是否在桌前（true/false）
- `is_study`: 是否在学习（true/false）
- `activity`: 当前活动（看书、用电脑等）
- `posture`: 坐姿（端正、不端正）
- `lighting`: 灯光（充足、不足）

### 时间调度配置

1. 访问配置页面
2. 启用"时间调度"
3. 设置每日自动开始/停止时间
4. 保存配置

系统会在指定时间自动启动/停止监控，每天只自动启动一次（如果因连续失败停止不会再次启动）。

### 查看检测记录

1. 访问 http://localhost:5000/records
2. 选择"今天的记录"或"最近的记录"
3. 点击图片可查看大图
4. 不合格的记录会以红色标记

## ⚠️ 重要说明

### 自动创建的目录

以下文件夹会在首次运行时自动创建：
- `data/` - 数据目录
- `data/captures/` - 截图保存目录
- `logs/` - 日志目录
- `config/` - 配置目录（包含 `monitor_config.json`）

### 从其他电脑迁移项目

**方法1：保留数据库和图片**
```bash
# 复制整个项目文件夹时，确保包含：
# - data/captures/ (图片文件)
# - data/detection_records.db (数据库)
# 否则记录页面会显示"图片不可用"
```

**方法2：清空数据重新开始**
```bash
# 删除数据文件夹，让应用重新创建
rm -rf data/
# 然后启动应用，会自动创建新的数据库
```

### Git 忽略的文件

以下文件/文件夹不会被提交到 Git：
- `.env` - 包含 API 密钥等敏感信息
- `data/captures/` - 图片文件太大且不断增长
- `data/*.db` - 数据库文件包含本地数据
- `logs/` - 日志文件

**配置文件会被提交**：
- `config/monitor_config.json` - 不包含敏感信息，应提交作为默认配置

## 🔧 开发说明

### 项目启动入口

```bash
# Web 界面（推荐）
cd web
python app.py

# 或者从根目录运行
python -m web.app
```

### 核心模块架构

```
┌─────────────────────────────────────────────┐
│           SimpleMonitorService              │
│        （监控服务 - 业务流程协调）            │
└─────────────────────────────────────────────┘
         │                │              │
         ▼                ▼              ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│VisionAnalyzer│  │RuleChecker   │  │NotifyManager │
│  (AI分析)    │  │ (规则检查)    │  │ (通知管理)    │
└──────────────┘  └──────────────┘  └──────────────┘
                                              │
                                              ▼
                                    ┌──────────────┐
                                    │  Messenger   │
                                    │ (消息发送)    │
                                    └──────────────┘
```

### 配置文件说明

- **`config/monitor_config.json`**：监控配置
  - 规则定义
  - 时间调度
  - 通知间隔
  - 预览设置

- **`.env`**：环境变量
  - API 密钥
  - 企业微信配置
  - Telegram 配置

### 关键特性

#### 1. 通知间隔控制

- **最小通知间隔**：两次通知之间的最短时间（避免频繁打扰）
- **最大通知间隔**：超过此时间即使合格也会发送状态更新
- **智能判断**：根据连续失败次数和上次通知时间综合判断

#### 2. 连续失败保护

- 达到连续失败限制后自动停止监控
- 避免持续消耗 API 配额
- 需要手动重新启动

#### 3. 实时预览

- 监控启动时短暂预览（可配置时长）
- 确认摄像头位置和角度
- 预览结束后自动进入监控模式

## 🐛 常见问题

### Q: 记录页面显示"图片不可用"

**A**: 原因是数据库中的记录指向不存在的图片文件。

**解决方案**：
1. 如果是从其他电脑复制的项目，需要同时复制 `data/captures/` 文件夹
2. 或者删除 `data/detection_records.db` 重新开始

### Q: 启动报错 "ModuleNotFoundError: No module named 'src'"

**A**: 确保从 `web/` 目录启动，或使用：
```bash
python -m web.app
```

### Q: 企业微信消息发送失败

**A**: 检查 `.env` 文件中的配置是否正确：
- `WECHAT_CORPID`：企业 ID
- `WECHAT_AGENTID`：应用 ID
- `WECHAT_SECRET`：应用 Secret
- `WECHAT_TOUSER`：收件人 userid（支持多个，用 `|` 分隔）

### Q: 摄像头无法打开

**A**：
1. 检查摄像头是否被其他应用占用
2. 检查摄像头索引（默认为 0，如需修改请编辑代码）
3. Windows 用户：确保已安装摄像头驱动

### Q: 监控停止后仍有截图日志

**A**: 已在最新版本中修复。监控停止时会：
1. 快速响应停止信号（最多 0.5 秒延迟）
2. 释放摄像头资源
3. 不会继续截图

如遇到此问题，请拉取最新代码。

## 🔄 更新日志

### v2.0 (最新)

- ✅ 修复监控停止时的竞态条件问题
- ✅ 优化停止响应速度（从等待完整周期改为最多 0.5 秒）
- ✅ 修复图片发送时的路径解析问题
- ✅ 修复 Web 图片显示的路径兼容性问题（Windows 反斜杠）
- ✅ 改进摄像头资源管理，确保正确释放

### v1.0

- 初始版本
- 基础监控功能
- Web 界面
- 企业微信通知

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

如有问题或建议，请提交 GitHub Issue。

---

<div align="center">

**Made with ❤️ for productive studying**

[⬆ 返回顶部](#study-buddy---ai-学习伙伴)

</div>
