# Study Buddy - AI Study Companion

<div align="center">

An intelligent AI-powered study monitoring system that uses computer vision to analyze study status in real-time, with a user-friendly web interface for rule configuration and monitoring management.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

English | [简体中文](README.md)

</div>

---

## ✨ Key Features

- 🎯 **Smart Analysis**: Uses Kimi Vision API to analyze study status
- 📸 **Real-time Monitoring**: Automatically captures study scene photos with configurable intervals
- 💬 **Smart Notifications**: Supports WeChat Work multi-recipient notifications with intelligent interval control
- 🖥️ **Web Management**: Visual configuration interface and real-time status monitoring
- ⚙️ **Flexible Rules**: Customize alert rules using regular expressions on the web page
- 📊 **History Records**: Complete study status history with red marking for failed checks
- ⏰ **Scheduled Tasks**: Automatic daily start/stop monitoring
- 🎥 **Live Preview**: Brief preview of camera feed on startup to ensure correct positioning
- 🛡️ **Smart Protection**: Automatically stops monitoring after consecutive failures reach limit

## 📁 Project Structure

```
study-buddy/
├── src/                    # Core business logic
│   ├── ai/                # AI analysis module
│   │   └── vision_analyzer.py
│   ├── messenger/         # Message notification module
│   │   ├── adapters/      # WeChat/Telegram adapters
│   │   └── messenger_service.py
│   ├── monitor/           # Monitoring service module
│   │   ├── simple_monitor_service.py
│   │   ├── notify_manager.py
│   │   └── simple_rule_checker.py
│   ├── storage/           # Storage module
│   │   └── detection_storage.py
│   ├── vision/            # Camera module
│   │   ├── camera_service.py
│   │   └── camera_singleton.py
│   └── common.py          # Common utilities
├── web/                   # Web interface
│   ├── app.py             # Flask application entry
│   ├── static/            # CSS, JS, static assets
│   └── templates/         # HTML templates
├── config/                # Configuration files
│   └── monitor_config.json
├── data/                  # Runtime data (ignored by Git)
│   ├── captures/          # Captured images
│   └── detection_records.db
├── logs/                  # Log files (ignored by Git)
├── .env                   # Environment variables (create from .env.example)
├── requirements.txt       # Python dependencies
├── README.md              # Chinese documentation
└── README_EN.md           # English documentation
```

## 🚀 Quick Start

### 1. Clone the Project

```bash
git clone https://github.com/eerenyuan/study-buddy.git
cd study-buddy
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

**Main Dependencies**:
- Python 3.8+
- Flask 2.0+
- OpenCV (cv2)
- Requests

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your configuration:

```bash
cp .env.example .env
```

Edit `.env` file with necessary configurations:

```env
# Kimi Vision API Configuration
KIMI_API_KEY=your_kimi_api_key_here

# WeChat Work Configuration
WECHAT_CORPID=your_corp_id
WECHAT_AGENTID=your_agent_id
WECHAT_SECRET=your_app_secret
WECHAT_TOUSER=RenYuan|xiaoyu

# Telegram Configuration (optional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

### 4. Launch the Application

```bash
cd web
python app.py
```

Visit http://localhost:5000

## 📝 Usage Guide

### First-Time Setup

1. **Start Application**: `cd web && python app.py`
2. **Visit Configuration Page**: http://localhost:5000/config
3. **Configure Monitoring Rules**:
   - Add rule fields (e.g., `at_desk`, `is_study`, `activity`, `posture`, `lighting`)
   - Set regular expressions (e.g., `^true$` means exact match "true")
   - Configure notification intervals and failure limits
4. **Configure Recipients**: http://localhost:5000/messenger_test
5. **Start Monitoring**: Click "Start Monitoring" on the homepage

### Monitoring Rules Example

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

**Rule Explanations**:
- `at_desk`: Whether at desk (true/false)
- `is_study`: Whether studying (true/false)
- `activity`: Current activity (reading, using computer, etc.)
- `posture`: Sitting posture (upright, not upright)
- `lighting`: Lighting condition (sufficient, insufficient)

### Time Scheduler Configuration

1. Visit the configuration page
2. Enable "Time Scheduler"
3. Set daily automatic start/stop times
4. Save configuration

The system will automatically start/stop monitoring at specified times, only auto-starting once per day (won't restart if stopped due to consecutive failures).

### Viewing Detection Records

1. Visit http://localhost:5000/records
2. Select "Today's Records" or "Recent Records"
3. Click on images to view full size
4. Failed records are marked in red

## ⚠️ Important Notes

### Automatically Created Directories

The following folders will be created automatically on first run:
- `data/` - Data directory
- `data/captures/` - Screenshot save directory
- `logs/` - Log directory
- `config/` - Configuration directory (contains `monitor_config.json`)

### Migrating Projects from Other Computers

**Method 1: Keep Database and Images**
```bash
# When copying the entire project folder, ensure you include:
# - data/captures/ (image files)
# - data/detection_records.db (database)
# Otherwise, the records page will show "Image unavailable"
```

**Method 2: Clear Data and Start Fresh**
```bash
# Delete the data folder and let the application recreate it
rm -rf data/
# Then start the application, it will create a new database automatically
```

### Git Ignored Files

The following files/folders won't be committed to Git:
- `.env` - Contains sensitive information like API keys
- `data/captures/` - Image files are too large and continuously growing
- `data/*.db` - Database files contain local data
- `logs/` - Log files

**Configuration Files ARE Committed**:
- `config/monitor_config.json` - Contains no sensitive info, should be committed as default config

## 🔧 Development Notes

### Project Entry Point

```bash
# Web interface (recommended)
cd web
python app.py

# Or run from root directory
python -m web.app
```

### Core Module Architecture

```
┌─────────────────────────────────────────────┐
│           SimpleMonitorService              │
│   (Monitoring Service - Orchestration)      │
└─────────────────────────────────────────────┘
         │                │              │
         ▼                ▼              ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│VisionAnalyzer│  │RuleChecker   │  │NotifyManager │
│  (AI Analysis)│  │ (Rule Check) │  │(Notify Mgmt) │
└──────────────┘  └──────────────┘  └──────────────┘
                                              │
                                              ▼
                                    ┌──────────────┐
                                    │  Messenger   │
                                    │(Msg Sending) │
                                    └──────────────┘
```

### Configuration File Descriptions

- **`config/monitor_config.json`**: Monitoring configuration
  - Rule definitions
  - Time scheduling
  - Notification intervals
  - Preview settings

- **`.env`**: Environment variables
  - API keys
  - WeChat Work configuration
  - Telegram configuration

### Key Features

#### 1. Notification Interval Control

- **Minimum notification interval**: Shortest time between notifications (avoid frequent disturbances)
- **Maximum notification interval**: Send status update even if qualified after this time
- **Smart judgment**: Comprehensive decision based on consecutive failures and last notification time

#### 2. Consecutive Failure Protection

- Automatically stops monitoring when consecutive failure limit is reached
- Avoids continuous consumption of API quota
- Requires manual restart

#### 3. Live Preview

- Brief preview on monitoring startup (configurable duration)
- Confirms camera position and angle
- Automatically enters monitoring mode after preview ends

## 🐛 Troubleshooting

### Q: Records page shows "Image unavailable"

**A**: The reason is that records in the database point to non-existent image files.

**Solutions**:
1. If you copied the project from another computer, you need to also copy the `data/captures/` folder
2. Or delete `data/detection_records.db` to start fresh

### Q: Startup error "ModuleNotFoundError: No module named 'src'"

**A**: Make sure to start from the `web/` directory, or use:
```bash
python -m web.app
```

### Q: WeChat Work message sending failed

**A**: Check if the configuration in `.env` file is correct:
- `WECHAT_CORPID`: Enterprise ID
- `WECHAT_AGENTID`: Application ID
- `WECHAT_SECRET`: Application Secret
- `WECHAT_TOUSER`: Recipient userid (multiple supported, separated by `|`)

### Q: Camera cannot be opened

**A**:
1. Check if the camera is being used by another application
2. Check camera index (default is 0, modify code if needed)
3. Windows users: Ensure camera driver is installed

### Q: Still see screenshot logs after monitoring stopped

**A**: This has been fixed in the latest version. When monitoring stops:
1. Quickly responds to stop signal (max 0.5 second delay)
2. Releases camera resources
3. Won't continue taking screenshots

If you encounter this issue, please pull the latest code.

## 🔄 Changelog

### v2.0 (Latest)

- ✅ Fixed race condition issue when monitoring stops
- ✅ Optimized stop response speed (from waiting full cycle to max 0.5 seconds)
- ✅ Fixed path resolution issue for image sending
- ✅ Fixed path compatibility issue for web image display (Windows backslashes)
- ✅ Improved camera resource management to ensure proper release

### v1.0

- Initial version
- Basic monitoring functionality
- Web interface
- WeChat Work notifications

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details

## 🤝 Contributing

Issues and Pull Requests are welcome!

## 📧 Contact

For questions or suggestions, please submit a GitHub Issue.

---

<div align="center">

**Made with ❤️ for productive studying**

[⬆ Back to Top](#study-buddy---ai-study-companion)

</div>
