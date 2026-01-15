# Study Buddy - AI 学习伙伴

基于 AI 视觉的智能学习陪伴系统，通过摄像头实时分析学习状态，并通过 Web 界面提供友好的规则配置和监控管理。

## ✨ 主要功能

- 🎯 **智能分析**: 使用 Kimi Vision API 分析学习状态
- 📸 **实时监控**: 自动捕获学习场景照片
- 💬 **智能通知**: 支持企业微信多收件人通知
- 🖥️ **Web 管理**: 可视化配置规则和监控界面
- ⚙️ **灵活规则**: Web 页面自定义提醒规则（正则表达式）
- 📊 **历史记录**: 完整的学习状态历史，不合格红色标记
- ⏰ **定时任务**: 每天自动启动和停止监控
- 🎥 **摄像头调试**: 实时查看摄像头画面

## 📁 项目结构

```
study-buddy/
├── src/                    # 核心业务逻辑
│   ├── ai/                # AI 分析模块
│   ├── messenger/         # 消息通知模块
│   ├── monitor/           # 监控服务模块
│   ├── storage/           # 存储模块
│   ├── vision/            # 摄像头模块
│   └── common.py          # 通用工具类
├── web/                   # Web 界面
│   ├── app.py             # Flask 应用
│   ├── static/            # CSS, JS
│   └── templates/         # HTML 模板
├── config/                # 配置文件
│   └── monitor_config.json
├── data/                  # 运行时数据（会被 Git 忽略）
│   ├── captures/          # 捕获的图片
│   └── detection_records.db
├── logs/                  # 日志文件（会被 Git 忽略）
├── .env                   # 环境变量（需要创建，见 .env.example）
├── requirements.txt       # Python 依赖
└── README.md
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
```

### 4. 启动应用

```bash
cd web
python app.py
```

访问 http://localhost:5000

## ⚠️ 重要说明

### 数据文件夹

以下文件夹会在首次运行时自动创建：
- `data/` - 数据目录
- `data/captures/` - 截图保存目录
- `logs/` - 日志目录
- `config/` - 配置目录（包含 `monitor_config.json`）

### 从其他电脑迁移项目

如果你从另一台电脑复制了这个项目：

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

### 数据不会被提交到 Git

以下文件/文件夹被 `.gitignore` 忽略（不会上传到 GitHub）：
- `.env` - 包含 API 密钥等敏感信息
- `data/captures/` - 图片文件太大且不断增长
- `data/*.db` - 数据库文件包含本地数据
- `logs/` - 日志文件

## 📝 使用说明

### 配置监控规则

1. 访问 http://localhost:5000/config
2. 添加规则（字段名 + 正则表达式）
3. 配置通知间隔和时间调度
4. 保存配置

### 测试消息通知

1. 访问 http://localhost:5000/messenger_test
2. 添加企业微信 userid
3. 点击"测试"按钮验证
4. 保存收件人列表

### 查看检测记录

1. 访问 http://localhost:5000/records
2. 选择"今天的记录"或"最近的记录"
3. 点击图片可查看大图

## 🔧 开发说明

### 项目启动入口

```bash
# Web 界面
cd web
python app.py

# 或者从根目录运行
python -m web.app
```

### 主要模块说明

- **SimpleMonitorService**: 核心监控服务
- **SimpleRuleChecker**: 规则检查器（正则匹配）
- **NotifyManager**: 通知管理器（间隔控制）
- **VisionAnalyzer**: AI 视觉分析
- **CameraSingleton**: 摄像头单例管理

### 配置文件

- `config/monitor_config.json` - 监控配置（规则、时间调度等）
- `.env` - 环境变量（API 密钥等）

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

**A**: 检查 `.env` 文件中的配置是否正确，特别是：
- `WECHAT_CORPID`
- `WECHAT_AGENTID`
- `WECHAT_SECRET`
- `WECHAT_TOUSER` (userid 格式)

## 📄 许可证

MIT License
