# StudyBuddy 学习伙伴

基于 AI 视觉的智能学习陪伴系统，通过摄像头实时分析孩子的学习状态，并通过 Web 界面提供友好的规则配置和监控管理。

## ✨ 特性

- 🎯 **智能分析**: 使用 Kimi Vision API 分析学习状态
- 📸 **实时监控**: 自动捕获学习场景照片
- 💬 **智能通知**: 支持企业微信多收件人通知
- 🖥️ **Web 管理**: 可视化配置规则和监控界面
- ⚙️ **灵活规则**: Web 页面自定义提醒规则（正则表达式）
- 📊 **历史记录**: 完整的学习状态历史，不合格红色标记

## 📁 项目结构

```
study-buddy/
├── core/                   # 核心模块
│   ├── __init__.py
│   ├── base.py            # 基础类定义
│   ├── config.py          # 环境变量管理（API keys）
│   └── scheduler.py       # 调度中心
├── modules/               # 功能模块
│   ├── vision/            # 视觉模块
│   │   └── __init__.py    # Camera + KimiVisionAnalyzer
│   └── im/                # 通知模块
│       └── __init__.py    # WeChatNotifier + IMManager
├── data/                  # 运行时数据
│   ├── captures/          # 捕获的图片
│   └── monitor_config.json # Web 保存的规则配置
├── logs/                  # 日志目录
├── main.py                # 命令行入口
├── web_server.py          # Web 管理界面
├── requirements.txt       # Python 依赖
├── .env.example           # 配置文件示例
└── .gitignore             # Git 忽略规则
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd study-buddy
pip install -r requirements.txt
```

### 2. 配置环境变量

复制配置文件并编辑：

```bash
cp .env.example .env
```

编辑 `.env` 文件，**只填入 API 凭证信息**：

```env
# Kimi Vision API
KIMI_API_KEY=your_kimi_api_key_here
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=moonshot-v1-8k-vision-preview
KIMI_TIMEOUT=120

# 企业微信配置
WECHAT_CORPID=your_corp_id
WECHAT_AGENTID=your_agent_id
WECHAT_SECRET=your_app_secret
WECHAT_TOUSER=user1|user2    # 多个用户用 | 分隔

# 摄像头配置
CAPTURE_INTERVAL=30
CAMERA_INDEX=0
RESOLUTION=1920,1080
IMAGE_QUALITY=85
```

### 3. 启动 Web 管理界面（推荐）

```bash
python web_server.py
```

访问：**http://localhost:5000**

Web 界面功能：
- 🎛️ 配置提醒规则（正则表达式）
- ⏱️ 配置监控间隔
- 📸 查看历史截图（不合格红色标记）
- 🎮 启动/停止监控
- 📊 实时状态显示

**规则配置示例**（在 Web 页面中修改）：
```
在书桌前: ^是$              # 必须在书桌前
正在玩耍: ^否$              # 不能玩耍
当前活动: ^(看书|写字)$      # 只能看书或写字
坐姿状态: ^端正$            # 坐姿必须端正
台灯状态: ^是$              # 必须开台灯
照明情况: ^(充足|一般)$     # 不能昏暗
```

### 4. 命令行运行（可选）

```bash
python main.py
```

使用 `.env` 中的配置运行。

## 🎯 核心功能

### 1. AI 视觉分析

Kimi Vision API 分析以下维度：
- ✅ 在书桌前检测
- ✅ 玩耍行为识别
- ✅ 当前活动识别（看书/写字/用电脑/玩手机/发呆）
- ✅ 坐姿状态检测（端正/不佳/趴着/歪坐）
- ✅ 台灯状态检测
- ✅ 照明情况分析

### 2. 智能提醒规则

在 **Web 页面**中配置正则表达式，系统会自动：
- ❌ 检查每项是否符合规则
- 🔴 不合格立即通知（文本+图片）
- ⏰ 定期发送状态更新
- 🛑 连续太久不合格自动停止

### 3. 多级通知机制

| 触发条件 | 操作 |
|---------|------|
| 规则检查不合格 | 立即通知（文本+图片）|
| 超过发送间隔 | 即使合格也通知 |
| 连续不合格超过停止间隔 | 通知并停止监控 |

### 4. 多收件人支持

```env
WECHAT_TOUSER=RenYuan|xiaoyu
```

## 📊 监控流程

```
启动监控 → 每30秒截图 → AI分析 → 检查规则
                                     ↓
                              ┌────┴────┐
                              │  合格？  │
                              └────┬────┘
                         是 ←──────┘ ↓ 否
                      更新last_correct  立即通知
                                        ↓
                                   检查是否该停止
```

## 📝 配置文件说明

### `.env` - 环境变量（需手动配置）

存放 **敏感信息**，不要提交到 Git：
- API keys
- 企业微信凭证
- 摄像头索引

### `data/monitor_config.json` - Web配置（自动生成）

Web 页面保存的配置：
- 提醒规则（正则表达式）
- 时间间隔

**此文件会被 .gitignore 忽略**

## 🔧 技术栈

- **Python 3.8+**
- **OpenCV**: 摄像头捕获
- **Kimi Vision API**: AI 图像分析
- **Flask**: Web 管理界面
- **企业微信 API**: 消息通知

## 📋 注意事项

1. **隐私保护**: 捕获的图片保存在 `data/captures/` 目录
2. **API 密钥**: `.env` 文件不要提交到 Git
3. **摄像头权限**: 确保程序有访问摄像头的权限
4. **网络要求**: Kimi Vision API 需要稳定的网络连接

## 🚀 未来扩展

- [ ] TTS 语音提醒模块
- [ ] 学习数据统计和可视化
- [ ] 多语言支持
- [ ] 更多通知渠道（钉钉、飞书等）

