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

from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.config import config
from core.scheduler import Scheduler
from modules.vision import create_vision_module
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
                print(f"[监控] 处理失败: {e}")
                import traceback
                traceback.print_exc()

            # 等待下一次捕获
            monitor_state["stop_event"].wait(monitor_config["intervals"]["capture"])

    finally:
        scheduler.shutdown()
        im_module.shutdown()
        vision_module["camera"].shutdown()
        vision_module["analyzer"].shutdown()
        print("[监控] 监控线程停止")


# HTML 模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>学习监工管理系统</title>
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
            <h1>🎓 学习监工管理系统</h1>
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
                <button type="button" class="btn btn-start" onclick="saveConfig()">保存配置</button>
            </form>
        </div>

        <div class="card">
            <h2>📸 历史记录</h2>
            <div id="history-container">
                <div class="loading">加载中...</div>
            </div>
        </div>
    </div>

    <script>
        // 加载配置
        async function loadConfig() {
            try {
                const res = await fetch('/api/config');
                const config = await res.json();

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

                const res = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ rules, intervals })
                });

                const data = await res.json();

                if (data.success) {
                    alert('配置已保存');
                } else {
                    alert('保存失败: ' + (data.error || '未知错误'));
                }
            } catch (e) {
                alert('请求失败: ' + e.message);
            }
        }

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


if __name__ == '__main__':
    print("=" * 60)
    print("学习监工 Web 管理界面")
    print("=" * 60)
    print(f"访问地址: http://localhost:5000")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
