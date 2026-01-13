"""
学习监工 Web 管理界面
提供配置、监控控制、历史记录查看功能
"""
import sys
import json
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Windows 控制台 UTF-8 编码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

from flask import Flask, render_template_string, request, jsonify, Response, stream_with_context
from flask_cors import CORS

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.config import config
from core.scheduler import Scheduler
from modules.vision import create_vision_module, Camera
from modules.im import create_im_module

app = Flask(__name__)
CORS(app)

# 全局状态
monitor_state = {
    "running": False,
    "last_capture_time": None,
    "last_notify_time": None,
    "last_correct_time": None,
    "history": [],
    "thread": None,
    "stop_event": threading.Event()
}

# 调试摄像头实例（用于视频流）
debug_camera = None
debug_camera_lock = threading.Lock()

# 定时任务调度器状态
scheduler_state = {
    "running": False,
    "thread": None,
    "stop_event": threading.Event(),
    "last_check": None
}

# 默认配置
default_config = {
    "rules": {
        "at_desk": r"^是$",
        "is_playing": r"^否$",
        "activity": r"^(看书|写字|用电脑)$",
        "posture": r"^端正$",
        "lamp_on": r"^是$",
        "lighting": r"^(充足|一般)$"
    },
    "intervals": {
        "capture": 30,      # 截图间隔（秒）
        "notify": 300,      # 图片发送间隔（秒）
        "stop": 3600        # 停止间隔（秒）
    },
    "schedule": {
        "enabled": False,   # 是否启用定时功能
        "start_time": "08:00",  # 开始时间（HH:MM 格式）
        "end_time": "18:00"     # 结束时间（HH:MM 格式）
    }
}

# 加载配置
config_file = project_root / "data" / "monitor_config.json"
if config_file.exists():
    with open(config_file, "r", encoding="utf-8") as f:
        monitor_config = json.load(f)
else:
    monitor_config = default_config.copy()
    config_file.parent.mkdir(exist_ok=True)
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(monitor_config, f, ensure_ascii=False, indent=2)


def save_config():
    """保存配置到文件"""
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(monitor_config, f, ensure_ascii=False, indent=2)


def check_rules(analysis: Dict[str, Any]) -> tuple[bool, list]:
    """检查分析结果是否符合规则

    Returns:
        (是否合格, 不合格的项列表)
    """
    failed_items = []
    rules = monitor_config["rules"]

    # 检查在书桌前
    value = "是" if analysis.get("at_desk") else "否"
    if not __import__("re").match(rules["at_desk"], value):
        failed_items.append("在书桌前")

    # 检查正在玩耍
    value = "是" if analysis.get("is_playing") else "否"
    if not __import__("re").match(rules["is_playing"], value):
        failed_items.append("正在玩耍")

    # 检查活动
    value = analysis.get("activity", "")
    if not __import__("re").match(rules["activity"], value):
        failed_items.append(f"活动: {value}")

    # 检查坐姿
    value = analysis.get("posture", "")
    if not __import__("re").match(rules["posture"], value):
        failed_items.append(f"坐姿: {value}")

    # 检查台灯
    value = "是" if analysis.get("lamp_on") else "否"
    if not __import__("re").match(rules["lamp_on"], value):
        failed_items.append("台灯")

    # 检查照明
    value = analysis.get("lighting", "")
    if not __import__("re").match(rules["lighting"], value):
        failed_items.append(f"照明: {value}")

    return len(failed_items) == 0, failed_items


def monitor_loop():
    """监控循环"""
    print("[监控] 监控线程启动")

    # 初始化模块
    vision_module = create_vision_module(config)
    vision_module["camera"].initialize()
    vision_module["analyzer"].initialize()

    im_module = create_im_module(config)
    im_module.initialize()

    scheduler = Scheduler(config, vision_module["analyzer"], im_module)
    scheduler.initialize()

    output_dir = Path("data/captures")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        while not monitor_state["stop_event"].is_set():
            # 捕获图像
            timestamp = datetime.now()
            image_path = output_dir / f"monitor_{int(time.time())}.jpg"

            try:
                captured_path = vision_module["camera"].capture(str(image_path))

                # 分析（不自动发送通知）
                analysis = vision_module["analyzer"].analyze(captured_path)
                scheduler.state_manager.update_state(analysis)

                # 检查规则
                is_correct, failed_items = check_rules(analysis)

                # 记录历史
                history_item = {
                    "timestamp": timestamp.isoformat(),
                    "image_path": str(captured_path),
                    "analysis": analysis,
                    "is_correct": is_correct,
                    "failed_items": failed_items
                }
                monitor_state["history"].append(history_item)
                monitor_state["last_capture_time"] = timestamp.isoformat()

                # 保留最近100条
                if len(monitor_state["history"]) > 100:
                    monitor_state["history"].pop(0)

                # 判断是否需要通知
                should_notify = False
                notify_reason = ""

                if not is_correct:
                    # 不合格，立即通知
                    should_notify = True
                    notify_reason = f"检查不合格: {', '.join(failed_items)}"
                else:
                    monitor_state["last_correct_time"] = timestamp.isoformat()

                # 检查发送间隔
                if monitor_state["last_notify_time"]:
                    last_notify = datetime.fromisoformat(monitor_state["last_notify_time"])
                    if (timestamp - last_notify).total_seconds() >= monitor_config["intervals"]["notify"]:
                        should_notify = True
                        notify_reason = "定期状态更新"

                # 检查停止间隔
                if monitor_state["last_correct_time"]:
                    last_correct = datetime.fromisoformat(monitor_state["last_correct_time"])
                    if (timestamp - last_correct).total_seconds() >= monitor_config["intervals"]["stop"]:
                        # 连续太长时间不合格，停止监控
                        stop_message = f"已连续{int((timestamp - last_correct).total_seconds())}秒没有正确学习，监控停止"
                        scheduler.im.notify(f"🚨 监控停止\n\n{stop_message}", "danger")
                        print(f"[监控] {stop_message}")
                        monitor_state["running"] = False
                        break

                # 发送通知
                if should_notify:
                    scheduler._send_notification(
                        {
                            "should_notify": True,
                            "notify_reason": notify_reason,
                            "notify_level": "danger" if not is_correct else "info",
                            "suggestion": analysis.get("suggestion", "")
                        },
                        captured_path
                    )
                    monitor_state["last_notify_time"] = timestamp.isoformat()

                print(f"[监控] {timestamp.strftime('%H:%M:%S')} - {'✓ 合格' if is_correct else '✗ 不合格'} - {failed_items if not is_correct else ''}")

            except Exception as e:
                error_msg = str(e)
                print(f"[监控] 处理失败: {error_msg}")

                # 如果是摄像头读取失败，尝试重新初始化
                if "摄像头" in error_msg or "无法从摄像头读取" in error_msg:
                    print("[监控] 检测到摄像头错误，尝试重新初始化...")
                    if vision_module["camera"].reinitialize():
                        print("[监控] 摄像头重新初始化成功")
                    else:
                        print("[监控] 摄像头重新初始化失败，将在下次尝试")
                        import traceback
                        traceback.print_exc()
                else:
                    import traceback
                    traceback.print_exc()

            # 等待下一次捕获
            monitor_state["stop_event"].wait(monitor_config["intervals"]["capture"])

    finally:
        monitor_state["running"] = False  # 确保状态被正确更新
        scheduler.shutdown()
        im_module.shutdown()
        vision_module["camera"].shutdown()
        vision_module["analyzer"].shutdown()
        print("[监控] 监控线程停止")


def scheduler_loop():
    """定时任务调度器循环"""
    print("[调度器] 定时任务调度器启动")

    # 记录今天是否已经启动过
    last_started_date = None

    while not scheduler_state["stop_event"].is_set():
        try:
            # 读取配置
            schedule_config = monitor_config.get("schedule", {})
            enabled = schedule_config.get("enabled", False)

            if enabled:
                # 获取当前时间和配置的时间
                now = datetime.now()
                current_date = now.date()
                current_time = now.strftime("%H:%M")
                start_time = schedule_config.get("start_time", "08:00")
                end_time = schedule_config.get("end_time", "18:00")

                # 检查是否应该启动监控（只在第一次到达时间时启动）
                if current_time >= start_time and current_time < end_time and not monitor_state["running"]:
                    # 检查今天是否已经启动过
                    if last_started_date != current_date:
                        print(f"[调度器] 到达开始时间 {start_time}，自动启动监控")
                        monitor_state["stop_event"].clear()
                        monitor_state["running"] = True
                        monitor_state["thread"] = threading.Thread(target=monitor_loop, daemon=True)
                        monitor_state["thread"].start()
                        last_started_date = current_date
                        print(f"[调度器] 监控已启动，当前时间: {current_time}")

                # 检查线程是否意外退出（比如初始化失败）
                if monitor_state["running"] and monitor_state["thread"]:
                    if not monitor_state["thread"].is_alive():
                        print(f"[调度器] 警告：监控线程意外退出，重置状态")
                        monitor_state["running"] = False
                        monitor_state["thread"] = None
                        last_started_date = None  # 允许重新启动

                # 检查是否应该停止监控
                elif current_time >= end_time and monitor_state["running"]:
                    print(f"[调度器] 到达结束时间 {end_time}，自动停止监控")
                    monitor_state["stop_event"].set()
                    monitor_state["running"] = False
                    last_started_date = None  # 重置，允许明天再次启动

            scheduler_state["last_check"] = datetime.now().isoformat()

            # 等待60秒再检查
            for _ in range(60):
                if scheduler_state["stop_event"].is_set():
                    break
                time.sleep(1)

        except Exception as e:
            print(f"[调度器] 错误: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(60)  # 出错后等待60秒再重试

    print("[调度器] 定时任务调度器停止")


def start_scheduler():
    """启动定时任务调度器"""
    if scheduler_state["running"]:
        return False

    scheduler_state["stop_event"].clear()
    scheduler_state["running"] = True
    scheduler_state["thread"] = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_state["thread"].start()
    print("[调度器] 定时任务调度器已启动")
    return True


def stop_scheduler():
    """停止定时任务调度器"""
    if not scheduler_state["running"]:
        return False

    scheduler_state["stop_event"].set()
    scheduler_state["running"] = False
    print("[调度器] 定时任务调度器已停止")
    return True


# 调试页面 HTML 模板
DEBUG_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>摄像头调试 - 学习监工</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #1a1a1a;
            color: #fff;
            padding: 20px;
        }
        .container {
            max-width: 1600px;
            margin: 0 auto;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px 30px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .header h1 {
            font-size: 24px;
            margin-bottom: 5px;
        }
        .header p {
            opacity: 0.9;
            font-size: 14px;
        }
        .video-container {
            background: #000;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            margin-bottom: 20px;
        }
        .video-wrapper {
            position: relative;
            width: 100%;
            padding-bottom: 56.25%; /* 16:9 aspect ratio */
            background: #000;
        }
        #video-feed {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: contain;
        }
        .status-bar {
            display: flex;
            gap: 15px;
            align-items: center;
            flex-wrap: wrap;
            padding: 15px;
            background: #2a2a2a;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .status-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 15px;
            background: #3a3a3a;
            border-radius: 6px;
            font-size: 14px;
        }
        .status-indicator {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #4caf50;
            animation: pulse 2s infinite;
        }
        .status-indicator.offline {
            background: #f44336;
            animation: none;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 600;
        }
        .btn-primary {
            background: #667eea;
            color: white;
        }
        .btn-primary:hover { background: #5568d3; }
        .btn-danger {
            background: #f44336;
            color: white;
        }
        .btn-danger:hover { background: #da190b; }
        .info-panel {
            background: #2a2a2a;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        .info-panel h2 {
            font-size: 18px;
            margin-bottom: 15px;
            color: #667eea;
            border-bottom: 1px solid #444;
            padding-bottom: 10px;
        }
        .info-item {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #333;
        }
        .info-item:last-child { border-bottom: none; }
        .info-label { color: #888; }
        .info-value { color: #fff; font-weight: 600; }
        .back-link {
            display: inline-block;
            margin-top: 20px;
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
        }
        .back-link:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎥 摄像头调试页面</h1>
            <p>实时查看摄像头画面，用于调试和配置</p>
        </div>

        <div class="video-container">
            <div class="video-wrapper">
                <img id="video-feed" alt="摄像头画面" style="display: none;" onerror="this.style.display='none'; document.getElementById('error-msg').style.display='block';">
            </div>
        </div>

        <div id="monitor-warning" style="display: none; text-align: center; padding: 40px; background: #ff9800; border-radius: 10px; margin-bottom: 20px;">
            <h3 style="color: #fff;">⚠️ 监控程序正在运行</h3>
            <p style="color: #fff; margin-top: 10px;">监控程序占用了摄像头，请先停止监控后再使用调试页面</p>
            <button class="btn btn-danger" onclick="stopMonitorAndReturn()" style="margin-top: 15px;">停止监控并刷新</button>
        </div>

        <div id="error-msg" style="display: none; text-align: center; padding: 40px; background: #2a2a2a; border-radius: 10px; margin-bottom: 20px;">
            <h3 style="color: #f44336;">❌ 摄像头连接失败</h3>
            <p style="color: #888; margin-top: 10px;">请检查摄像头是否正常工作</p>
        </div>

        <div class="status-bar">
            <div class="status-item">
                <span class="status-indicator" id="status-indicator"></span>
                <span id="status-text">连接中...</span>
            </div>
            <div class="status-item">
                <span>分辨率: <strong id="resolution">检测中...</strong></span>
            </div>
            <div class="status-item">
                <span>FPS: <strong id="fps">计算中...</strong></span>
            </div>
            <button class="btn btn-primary" onclick="location.reload()">重新连接</button>
            <button class="btn btn-danger" onclick="closeCamera()">关闭摄像头</button>
        </div>

        <div class="info-panel">
            <h2>📋 摄像头信息</h2>
            <div class="info-item">
                <span class="info-label">设备索引</span>
                <span class="info-value">0 (默认摄像头)</span>
            </div>
            <div class="info-item">
                <span class="info-label">目标分辨率</span>
                <span class="info-value">1920 x 1080</span>
            </div>
            <div class="info-item">
                <span class="info-label">图像质量</span>
                <span class="info-value">85 (JPEG)</span>
            </div>
            <div class="info-item">
                <span class="info-label">缓冲区大小</span>
                <span class="info-value">1 (低延迟)</span>
            </div>
            <div class="info-item">
                <span class="info-label">使用说明</span>
                <span class="info-value">用于调试摄像头位置和角度</span>
            </div>
        </div>

        <a href="/" class="back-link">← 返回主页面</a>
    </div>

    <script>
        const img = document.getElementById('video-feed');
        const statusIndicator = document.getElementById('status-indicator');
        const statusText = document.getElementById('status-text');
        const resolutionEl = document.getElementById('resolution');
        const fpsEl = document.getElementById('fps');
        const monitorWarning = document.getElementById('monitor-warning');

        let frameCount = 0;
        let lastTime = Date.now();

        // 检查监控状态
        async function checkMonitorStatus() {
            try {
                console.log('[Debug] 检查监控状态...');
                const res = await fetch('/api/status');
                const data = await res.json();
                console.log('[Debug] 监控状态:', data);

                if (data.running) {
                    // 监控正在运行，显示警告
                    console.log('[Debug] 监控正在运行，显示警告');
                    monitorWarning.style.display = 'block';
                    statusText.textContent = '监控运行中';
                    statusIndicator.classList.add('offline');
                    return false;
                } else {
                    // 监控未运行，启动视频流
                    console.log('[Debug] 监控未运行，启动视频流');
                    monitorWarning.style.display = 'none';

                    // 强制重新设置视频源，确保使用正确的URL
                    console.log('[Debug] 设置视频源');
                    img.style.display = 'block';
                    img.src = '/video_feed?t=' + Date.now();

                    return true;
                }
            } catch (e) {
                console.error('[Debug] 检查监控状态失败:', e);
                statusText.textContent = '检查失败';
                statusIndicator.classList.add('offline');
                return false;
            }
        }

        // 停止监控并刷新页面
        async function stopMonitorAndReturn() {
            try {
                const res = await fetch('/api/stop', { method: 'POST' });
                const data = await res.json();

                if (data.success) {
                    // 等待1秒后刷新页面
                    setTimeout(() => location.reload(), 1000);
                } else {
                    alert('停止监控失败: ' + (data.error || '未知错误'));
                }
            } catch (e) {
                alert('请求失败: ' + e.message);
            }
        }

        img.onload = function() {
            statusIndicator.classList.remove('offline');
            statusText.textContent = '运行中';
            resolutionEl.textContent = img.naturalWidth + ' x ' + img.naturalHeight;

            // 计算 FPS
            frameCount++;
            const now = Date.now();
            const elapsed = (now - lastTime) / 1000;
            if (elapsed >= 1) {
                fpsEl.textContent = Math.round(frameCount / elapsed);
                frameCount = 0;
                lastTime = now;
            }
        };

        img.onerror = function() {
            statusIndicator.classList.add('offline');
            statusText.textContent = '离线';
        };

        function closeCamera() {
            if (confirm('确定要关闭摄像头吗？')) {
                fetch('/api/debug_camera', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'close' })
                }).then(() => {
                    img.src = '';
                    img.style.display = 'none';
                    statusIndicator.classList.add('offline');
                    statusText.textContent = '已关闭';
                });
            }
        }

        // 页面加载时检查监控状态
        checkMonitorStatus();

        // 定期检查连接状态
        setInterval(() => {
            if (img.complete && img.naturalWidth === 0) {
                statusIndicator.classList.add('offline');
                statusText.textContent = '离线';
            }
        }, 5000);
    </script>
</body>
</html>
"""


# HTML 模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>StudyBuddy学习伙伴</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .header h1 { font-size: 28px; margin-bottom: 10px; }
        .status-bar {
            display: flex;
            gap: 20px;
            align-items: center;
            flex-wrap: wrap;
        }
        .status-item {
            background: rgba(255,255,255,0.2);
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 14px;
        }
        .status-running { background: rgba(76, 175, 80, 0.3); }
        .status-stopped { background: rgba(244, 67, 54, 0.3); }
        .btn {
            padding: 12px 30px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 600;
        }
        .btn-start {
            background: #4caf50;
            color: white;
        }
        .btn-start:hover { background: #45a049; }
        .btn-stop {
            background: #f44336;
            color: white;
        }
        .btn-stop:hover { background: #da190b; }
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .card {
            background: white;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .card h2 {
            font-size: 20px;
            margin-bottom: 20px;
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        .form-group { margin-bottom: 15px; }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
            color: #555;
        }
        .form-group input {
            width: 100%;
            padding: 10px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            font-size: 14px;
        }
        .form-group input:focus {
            outline: none;
            border-color: #667eea;
        }
        .form-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
        }
        .history-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 15px;
        }
        .history-item {
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            overflow: hidden;
            transition: transform 0.3s;
        }
        .history-item:hover {
            transform: translateY(-5px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        .history-item.failed {
            border-color: #f44336;
            box-shadow: 0 0 10px rgba(244, 67, 54, 0.3);
        }
        .history-item img {
            width: 100%;
            height: 150px;
            object-fit: cover;
        }
        .history-info {
            padding: 10px;
            font-size: 12px;
        }
        .history-time {
            font-weight: 600;
            color: #667eea;
            margin-bottom: 5px;
        }
        .history-status {
            color: #4caf50;
        }
        .history-item.failed .history-status {
            color: #f44336;
        }
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #999;
        }
        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            margin-left: 10px;
        }
        .badge-success { background: #4caf50; color: white; }
        .badge-danger { background: #f44336; color: white; }
        .loading {
            text-align: center;
            padding: 20px;
            color: #999;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎓 StudyBuddy学习伙伴 <a href="/debug" style="font-size: 16px; margin-left: 20px; color: white; text-decoration: none; opacity: 0.8;">🎥 摄像头调试</a></h1>
            <div class="status-bar">
                <div class="status-item" id="status-display">
                    状态: <span id="status-text">未启动</span>
                </div>
                <div class="status-item">
                    最后捕获: <span id="last-capture">无</span>
                </div>
                <div class="status-item">
                    最后通知: <span id="last-notify">无</span>
                </div>
                <button class="btn btn-start" id="btn-start" onclick="startMonitor()">启动监控</button>
                <button class="btn btn-stop" id="btn-stop" onclick="stopMonitor()" disabled>停止监控</button>
                <button class="btn" onclick="location.reload()">刷新</button>
            </div>
        </div>

        <div class="card">
            <h2>⚙️ 报警规则配置</h2>
            <form id="config-form">
                <div class="form-row">
                    <div class="form-group">
                        <label>在书桌前 (正则)</label>
                        <input type="text" name="at_desk" value="^是$" placeholder="例如: ^是$">
                    </div>
                    <div class="form-group">
                        <label>正在玩耍 (正则)</label>
                        <input type="text" name="is_playing" value="^否$" placeholder="例如: ^否$">
                    </div>
                    <div class="form-group">
                        <label>当前活动 (正则)</label>
                        <input type="text" name="activity" value="^(看书|写字|用电脑)$" placeholder="例如: ^(看书|写字|用电脑)$">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>坐姿状态 (正则)</label>
                        <input type="text" name="posture" value="^端正$" placeholder="例如: ^端正$">
                    </div>
                    <div class="form-group">
                        <label>台灯状态 (正则)</label>
                        <input type="text" name="lamp_on" value="^是$" placeholder="例如: ^是$">
                    </div>
                    <div class="form-group">
                        <label>照明情况 (正则)</label>
                        <input type="text" name="lighting" value="^(充足|一般)$" placeholder="例如: ^(充足|一般)$">
                    </div>
                </div>
            </form>
        </div>

        <div class="card">
            <h2>⏱️ 时间间隔配置</h2>
            <form id="intervals-form">
                <div class="form-row">
                    <div class="form-group">
                        <label>截图间隔 (秒)</label>
                        <input type="number" name="capture" value="30" min="5">
                    </div>
                    <div class="form-group">
                        <label>图片发送间隔 (秒)</label>
                        <input type="number" name="notify" value="300" min="30">
                    </div>
                    <div class="form-group">
                        <label>停止间隔 (秒)</label>
                        <input type="number" name="stop" value="3600" min="60">
                    </div>
                </div>
            </form>
        </div>

        <div class="card">
            <h2>⏰ 定时任务配置</h2>
            <form id="schedule-form">
                <div class="form-row">
                    <div class="form-group">
                        <label style="display: flex; align-items: center; gap: 10px;">
                            <input type="checkbox" name="enabled" id="schedule-enabled">
                            <span>启用定时任务</span>
                        </label>
                        <small style="color: #666; display: block; margin-top: 5px;">
                            启用后，系统会在每天指定时间自动启动和停止监控
                        </small>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>开始时间</label>
                        <input type="time" name="start_time" value="08:00">
                        <small style="color: #666;">每天自动启动监控的时间</small>
                    </div>
                    <div class="form-group">
                        <label>结束时间</label>
                        <input type="time" name="end_time" value="18:00">
                        <small style="color: #666;">每天自动停止监控的时间</small>
                    </div>
                </div>
                <div id="schedule-status" style="padding: 10px; background: #f0f0f0; border-radius: 5px; margin-top: 10px;">
                    <strong>下次执行：</strong>
                    <span id="next-schedule">未启用</span>
                </div>
            </form>
        </div>

        <div class="card">
            <h2>📸 历史记录</h2>
            <div id="history-container">
                <div class="loading">加载中...</div>
            </div>
        </div>

        <!-- 统一的保存按钮区域 -->
        <div style="position: fixed; bottom: 0; left: 0; right: 0; background: white; padding: 15px; box-shadow: 0 -2px 10px rgba(0,0,0,0.1); text-align: center;">
            <button id="save-config-btn" type="button" class="btn btn-start" onclick="saveConfig()" disabled style="padding: 15px 40px; font-size: 16px;">
                💾 保存配置
            </button>
            <span id="save-status" style="margin-left: 15px; color: #666;"></span>
        </div>
    </div>

    <style>
        /* 为底部固定按钮留出空间 */
        body { padding-bottom: 80px; }
    </style>

    <script>
        // 存储原始配置，用于检测变更
        let originalConfig = null;

        // 检查配置是否有变更
        function checkConfigChanged() {
            if (!originalConfig) return false;

            const currentRules = {};
            document.querySelectorAll('#config-form input').forEach(input => {
                currentRules[input.name] = input.value;
            });

            const currentIntervals = {};
            document.querySelectorAll('#intervals-form input').forEach(input => {
                currentIntervals[input.name] = parseInt(input.value);
            });

            const currentSchedule = {
                enabled: document.getElementById('schedule-enabled').checked,
                start_time: document.querySelector('input[name="start_time"]').value,
                end_time: document.querySelector('input[name="end_time"]').value
            };

            // 比较配置
            const rulesChanged = JSON.stringify(currentRules) !== JSON.stringify(originalConfig.rules);
            const intervalsChanged = JSON.stringify(currentIntervals) !== JSON.stringify(originalConfig.intervals);
            const scheduleChanged = JSON.stringify(currentSchedule) !== JSON.stringify(originalConfig.schedule || { enabled: false });

            return rulesChanged || intervalsChanged || scheduleChanged;
        }

        // 更新保存按钮状态
        function updateSaveButton() {
            const btn = document.getElementById('save-config-btn');
            const status = document.getElementById('save-status');

            if (checkConfigChanged()) {
                btn.disabled = false;
                btn.textContent = '💾 保存配置';
                status.textContent = '⚠️ 配置已修改，请保存';
                status.style.color = '#f39c12';
            } else {
                btn.disabled = true;
                btn.textContent = '💾 保存配置';
                status.textContent = '✓ 配置已是最新';
                status.style.color = '#27ae60';
            }
        }

        // 加载配置
        async function loadConfig() {
            try {
                const res = await fetch('/api/config');
                const config = await res.json();

                // 保存原始配置
                originalConfig = JSON.parse(JSON.stringify(config));

                // 填充规则表单
                document.querySelectorAll('#config-form input').forEach(input => {
                    if (config.rules && config.rules[input.name]) {
                        input.value = config.rules[input.name];
                    }
                });

                // 填充间隔表单
                document.querySelectorAll('#intervals-form input').forEach(input => {
                    if (config.intervals && config.intervals[input.name] !== undefined) {
                        input.value = config.intervals[input.name];
                    }
                });

                // 填充定时任务表单
                if (config.schedule) {
                    document.getElementById('schedule-enabled').checked = config.schedule.enabled || false;
                    if (config.schedule.start_time) {
                        document.querySelector('input[name="start_time"]').value = config.schedule.start_time;
                    }
                    if (config.schedule.end_time) {
                        document.querySelector('input[name="end_time"]').value = config.schedule.end_time;
                    }
                    updateNextSchedule();
                }

                // 更新保存按钮状态
                updateSaveButton();

            } catch (e) {
                console.error('加载配置失败:', e);
            }
        }

        // 获取状态
        async function getStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();

                // 更新状态显示
                const statusText = document.getElementById('status-text');
                const statusDisplay = document.getElementById('status-display');
                const btnStart = document.getElementById('btn-start');
                const btnStop = document.getElementById('btn-stop');

                if (data.running) {
                    statusText.textContent = '运行中';
                    statusDisplay.className = 'status-item status-running';
                    btnStart.disabled = true;
                    btnStop.disabled = false;
                } else {
                    statusText.textContent = '已停止';
                    statusDisplay.className = 'status-item status-stopped';
                    btnStart.disabled = false;
                    btnStop.disabled = true;
                }

                document.getElementById('last-capture').textContent = data.last_capture || '无';
                document.getElementById('last-notify').textContent = data.last_notify || '无';

                // 更新历史记录
                renderHistory(data.history);

            } catch (e) {
                console.error('获取状态失败:', e);
            }
        }

        // 渲染历史记录
        function renderHistory(history) {
            const container = document.getElementById('history-container');

            if (!history || history.length === 0) {
                container.innerHTML = '<div class="empty-state">暂无历史记录</div>';
                return;
            }

            container.innerHTML = '<div class="history-grid">' + history.map(item => `
                <div class="history-item ${item.is_correct ? '' : 'failed'}">
                    <img src="/image/${encodeURIComponent(item.image_path)}" alt="截图">
                    <div class="history-info">
                        <div class="history-time">${new Date(item.timestamp).toLocaleString('zh-CN')}</div>
                        <div class="history-status">
                            ${item.is_correct ? '✓ 合格' : '✗ 不合格'}
                            ${!item.is_correct && item.failed_items ? `<br><span style="color:#f44336">${item.failed_items.join(', ')}</span>` : ''}
                        </div>
                    </div>
                </div>
            `).join('') + '</div>';
        }

        // 启动监控
        async function startMonitor() {
            try {
                const res = await fetch('/api/start', { method: 'POST' });
                const data = await res.json();

                if (data.success) {
                    alert('监控已启动');
                    getStatus();
                } else {
                    alert('启动失败: ' + (data.error || '未知错误'));
                }
            } catch (e) {
                alert('请求失败: ' + e.message);
            }
        }

        // 停止监控
        async function stopMonitor() {
            if (!confirm('确定要停止监控吗？')) return;

            try {
                const res = await fetch('/api/stop', { method: 'POST' });
                const data = await res.json();

                if (data.success) {
                    alert('监控已停止');
                    getStatus();
                } else {
                    alert('停止失败: ' + (data.error || '未知错误'));
                }
            } catch (e) {
                alert('请求失败: ' + e.message);
            }
        }

        // 保存配置
        async function saveConfig() {
            try {
                // 收集规则
                const rules = {};
                document.querySelectorAll('#config-form input').forEach(input => {
                    rules[input.name] = input.value;
                });

                // 收集间隔
                const intervals = {};
                document.querySelectorAll('#intervals-form input').forEach(input => {
                    intervals[input.name] = parseInt(input.value);
                });

                // 收集定时任务配置
                const schedule = {
                    enabled: document.getElementById('schedule-enabled').checked,
                    start_time: document.querySelector('input[name="start_time"]').value,
                    end_time: document.querySelector('input[name="end_time"]').value
                };

                const res = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ rules, intervals, schedule })
                });

                const data = await res.json();

                if (data.success) {
                    // 更新原始配置
                    originalConfig = {
                        rules: rules,
                        intervals: intervals,
                        schedule: schedule
                    };

                    // 更新按钮状态
                    const btn = document.getElementById('save-config-btn');
                    const status = document.getElementById('save-status');
                    btn.disabled = true;
                    status.textContent = '✓ 配置已保存';
                    status.style.color = '#27ae60';

                    // 3秒后隐藏状态
                    setTimeout(() => {
                        status.textContent = '✓ 配置已是最新';
                    }, 3000);

                    updateNextSchedule();

                    // 刷新状态（因为保存配置可能会触发自动启动/停止监控）
                    await getStatus();
                } else {
                    alert('保存失败: ' + (data.error || '未知错误'));
                }
            } catch (e) {
                alert('请求失败: ' + e.message);
            }
        }

        // 更新下次执行时间显示
        function updateNextSchedule() {
            const enabled = document.getElementById('schedule-enabled').checked;
            const nextScheduleEl = document.getElementById('next-schedule');

            if (!enabled) {
                nextScheduleEl.textContent = '未启用';
                return;
            }

            const startTime = document.querySelector('input[name="start_time"]').value;
            const endTime = document.querySelector('input[name="end_time"]').value;

            // 计算下次启动和停止时间
            const now = new Date();
            const todayStart = new Date(now);
            const [startHour, startMin] = startTime.split(':');
            todayStart.setHours(parseInt(startHour), parseInt(startMin), 0, 0);

            const todayEnd = new Date(now);
            const [endHour, endMin] = endTime.split(':');
            todayEnd.setHours(parseInt(endHour), parseInt(endMin), 0, 0);

            let nextStart, nextEnd;

            if (now < todayStart) {
                // 今天还没到开始时间
                nextStart = todayStart;
                nextEnd = todayEnd;
            } else if (now < todayEnd) {
                // 今天在监控时间段内
                nextStart = todayStart;
                nextEnd = todayEnd;
            } else {
                // 今天已经过了结束时间，下次是明天
                nextStart = new Date(todayStart);
                nextStart.setDate(nextStart.getDate() + 1);
                nextEnd = new Date(todayEnd);
                nextEnd.setDate(nextEnd.getDate() + 1);
            }

            const formatTime = (d) => {
                return d.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
            };

            nextScheduleEl.textContent = `启动: ${formatTime(nextStart)} | 停止: ${formatTime(nextEnd)}`;
        }

        // 监听所有配置输入变化
        document.addEventListener('DOMContentLoaded', () => {
            // 监听规则表单输入
            document.querySelectorAll('#config-form input').forEach(input => {
                input.addEventListener('input', updateSaveButton);
            });

            // 监听间隔表单输入
            document.querySelectorAll('#intervals-form input').forEach(input => {
                input.addEventListener('input', updateSaveButton);
            });

            // 监听定时任务配置
            document.getElementById('schedule-enabled').addEventListener('change', () => {
                updateNextSchedule();
                updateSaveButton();
            });
            document.querySelector('input[name="start_time"]').addEventListener('change', () => {
                updateNextSchedule();
                updateSaveButton();
            });
            document.querySelector('input[name="end_time"]').addEventListener('change', () => {
                updateNextSchedule();
                updateSaveButton();
            });
        });

        // 初始加载
        loadConfig();  // 先加载配置
        getStatus();   // 再获取状态

        // 定时刷新状态（不刷新配置，避免用户正在编辑时被打断）
        setInterval(getStatus, 5000);
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """主页"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/status')
def get_status():
    """获取状态"""
    return jsonify({
        "running": monitor_state["running"],
        "last_capture": monitor_state["last_capture_time"],
        "last_notify": monitor_state["last_notify_time"],
        "history": monitor_state["history"][-20:]  # 最近20条
    })


@app.route('/api/start', methods=['POST'])
def start_monitor():
    """启动监控"""
    if monitor_state["running"]:
        return jsonify({"success": False, "error": "监控已在运行中"})

    monitor_state["stop_event"].clear()
    monitor_state["running"] = True

    # 启动监控线程
    monitor_state["thread"] = threading.Thread(target=monitor_loop, daemon=True)
    monitor_state["thread"].start()

    return jsonify({"success": True})


@app.route('/api/stop', methods=['POST'])
def stop_monitor():
    """停止监控"""
    if not monitor_state["running"]:
        return jsonify({"success": False, "error": "监控未运行"})

    monitor_state["stop_event"].set()
    monitor_state["running"] = False

    return jsonify({"success": True})


@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    """配置管理"""
    if request.method == 'GET':
        return jsonify(monitor_config)
    else:
        try:
            data = request.json
            monitor_config["rules"].update(data.get("rules", {}))
            monitor_config["intervals"].update(data.get("intervals", {}))

            # 处理定时任务配置
            if "schedule" in data:
                old_enabled = monitor_config.get("schedule", {}).get("enabled", False)
                monitor_config["schedule"] = data["schedule"]
                new_enabled = data["schedule"].get("enabled", False)

                # 如果定时任务配置发生变化，重启调度器
                if old_enabled != new_enabled:
                    if new_enabled:
                        start_scheduler()
                        print("[配置] 定时任务已启用")
                    else:
                        stop_scheduler()
                        print("[配置] 定时任务已禁用")

            save_config()
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})


@app.route('/image/<path:image_path>')
def serve_image(image_path):
    """提供图片"""
    from flask import send_file
    # 解码URL路径
    import urllib.parse
    image_path = urllib.parse.unquote(image_path)
    return send_file(image_path)


@app.route('/debug')
def debug():
    """调试页面 - 实时摄像头画面"""
    return render_template_string(DEBUG_HTML_TEMPLATE)


@app.route('/video_feed')
def video_feed():
    """视频流接口"""
    print("[视频流] 客户端连接")
    def generate():
        global debug_camera

        with debug_camera_lock:
            if debug_camera is None:
                print("[视频流] 初始化摄像头")
                debug_camera = Camera(config)
                if not debug_camera.initialize():
                    print("[视频流] 摄像头初始化失败")
                    yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + create_error_image() + b'\r\n'
                    return
                print("[视频流] 摄像头初始化成功")

        if debug_camera is None or debug_camera.cap is None:
            # 摄像头初始化失败
            print("[视频流] 摄像头对象为空")
            yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + create_error_image() + b'\r\n'
            return

        try:
            import cv2
            print("[视频流] 开始推流")

            frame_count = 0
            start_time = time.time()

            while True:
                with debug_camera_lock:
                    # 检查摄像头是否被关闭
                    if debug_camera is None or debug_camera.cap is None or not debug_camera.cap.isOpened():
                        print("[视频流] 摄像头未打开或已关闭")
                        break

                    # 清空缓冲区，读取最新帧（减少延迟）
                    debug_camera.cap.read()

                    ret, frame = debug_camera.cap.read()

                    if not ret:
                        print("[视频流] 读取帧失败")
                        break

                # 编码为 JPEG
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if not ret:
                    continue

                frame_bytes = buffer.tobytes()
                frame_count += 1

                # 生成 MJPEG 流
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

                # 第一帧输出时间（在yield之后，确保数据已发送）
                if frame_count == 1:
                    elapsed = time.time() - start_time
                    print(f"[视频流] 首帧延迟: {elapsed:.2f}秒")

                if frame_count % 30 == 0:
                    print(f"[视频流] 已发送 {frame_count} 帧")

        except GeneratorExit:
            print("[视频流] 客户端断开连接")
        except Exception as e:
            print(f"[视频流] 错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            pass  # 保持摄像头打开以便快速重连

    return Response(stream_with_context(generate()),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/debug_camera', methods=['POST'])
def control_debug_camera():
    """控制调试摄像头"""
    global debug_camera

    action = request.json.get('action')

    if action == 'close':
        with debug_camera_lock:
            if debug_camera:
                debug_camera.shutdown()
                debug_camera = None
                print("[视频流] 摄像头已手动关闭")
        return jsonify({"success": True, "message": "摄像头已关闭"})

    return jsonify({"success": False, "error": "未知操作"})


def create_error_image():
    """创建错误提示图片"""
    from PIL import Image, ImageDraw, ImageFont
    import io

    img = Image.new('RGB', (640, 480), color='#333')
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 30)
    except:
        font = ImageFont.load_default()

    text = "Camera Not Available"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (640 - text_width) // 2
    y = (480 - text_height) // 2

    draw.text((x, y), text, fill='white', font=font)

    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    return buffer.getvalue()


if __name__ == '__main__':
    print("=" * 60)
    print("学习监工 Web 管理界面")
    print("=" * 60)
    print(f"访问地址: http://localhost:5000")
    print("=" * 60)

    # 启动定时任务调度器
    if monitor_config.get("schedule", {}).get("enabled", False):
        start_scheduler()

    app.run(host='0.0.0.0', port=5000, debug=True)
