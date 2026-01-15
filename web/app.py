"""
Web Application - Study Buddy System

使用 Flask 提供 Web 界面和 RESTful API
"""
import sys
from pathlib import Path

# 添加父目录到 sys.path，以便导入 src 模块
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, render_template, jsonify, request, Response, stream_with_context
import cv2
import time
import threading
import os

from src.monitor import create_simple_monitor_service
from src.ai import create_ai_service, AIConfig
from src.vision import get_camera_singleton, get_camera_service, CameraServiceConfig
from src.messenger import create_messenger_service, MessengerConfig
from src.storage import get_detection_record_service
from src.common import Config


# 创建 Flask 应用
app = Flask(__name__,
            template_folder='templates',
            static_folder='static')

# 全局变量
monitor_service = None
services = {}
preview_active = False  # 是否在预览阶段
preview_start_time = None  # 预览开始时间
preview_duration = 10  # 预览持续时间（秒）
preview_lock = threading.Lock()


def init_services():
    """初始化所有服务"""
    global monitor_service, services

    if monitor_service is not None:
        return monitor_service

    # 1. AI 服务
    ai_config = AIConfig(
        api_key=os.getenv("KIMI_API_KEY"),
        base_url="https://api.moonshot.cn/v1",
        vision_model="moonshot-v1-8k-vision-preview"
    )
    ai_service = create_ai_service(ai_config)
    vision_analyzer = ai_service.vision()

    # 2. Camera 服务
    camera_config_obj = Config()
    camera_singleton = get_camera_singleton(camera_config_obj)
    camera_service_config = CameraServiceConfig(
        preview_timeout=300,
        log_dir=str(PROJECT_ROOT / "logs")
    )
    camera_service = get_camera_service(camera_singleton, camera_service_config)

    # 3. Messenger 服务
    messenger_config = MessengerConfig(
        wechat_corpid=os.getenv("WECHAT_CORPID", ""),
        wechat_secret=os.getenv("WECHAT_SECRET", ""),
        wechat_agentid=os.getenv("WECHAT_AGENTID", ""),
        wechat_recipient=os.getenv("WECHAT_TOUSER", ""),
        telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "")
    )
    messenger_service = create_messenger_service(messenger_config)

    # 4. Storage 服务
    storage_service = get_detection_record_service(db_path=str(PROJECT_ROOT / "data" / "detection_records.db"))

    # 5. Monitor 服务
    config_file = str(PROJECT_ROOT / "config" / "monitor_config.json")
    monitor_service = create_simple_monitor_service(
        vision_analyzer=vision_analyzer,
        messenger_service=messenger_service,
        camera_service=camera_service,
        storage_service=storage_service,
        config_file=config_file
    )

    services = {
        "ai": ai_service,
        "camera": camera_service,
        "messenger": messenger_service,
        "storage": storage_service,
        "monitor": monitor_service
    }

    # 如果配置中启用了时间调度，启动时间调度器
    if monitor_service.config.enable_time_scheduler:
        print(f"[系统] 启动时间调度器 - 开始: {monitor_service.config.auto_start_time}, 停止: {monitor_service.config.auto_stop_time}")
        monitor_service.start_time_scheduler()

    return monitor_service


# ==================== 页面路由 ====================

@app.route('/')
def index():
    """主页 - 显示系统状态"""
    monitor = init_services()
    status = monitor.get_status()

    return render_template('index.html',
                         is_monitoring=status['is_monitoring'],
                         consecutive_failures=status['consecutive_failures'],
                         consecutive_fail_limit=status['notify_manager']['consecutive_fail_limit'])


@app.route('/config')
def config_page():
    """配置页面"""
    # 直接从配置文件加载（确保显示最新的配置）
    from src.monitor import MonitorConfig
    config_file = str(PROJECT_ROOT / "config" / "monitor_config.json")
    config = MonitorConfig.load(config_file)

    return render_template('config.html',
                         rules=config.rules,
                         min_notify_interval=config.min_notify_interval,
                         max_notify_interval=config.max_notify_interval,
                         consecutive_fail_limit=config.consecutive_fail_limit,
                         capture_interval=config.capture_interval,
                         preview_duration=config.preview_duration,
                         enable_preview=config.enable_preview,
                         auto_start_time=config.auto_start_time or "",
                         auto_stop_time=config.auto_stop_time or "",
                         enable_time_scheduler=config.enable_time_scheduler)


@app.route('/records')
def records_page():
    """记录页面"""
    return render_template('records.html')


@app.route('/messenger_test')
def messenger_test_page():
    """消息测试页面"""
    # 从环境变量读取当前配置的收件人
    current_recipients = os.getenv("WECHAT_TOUSER", "")

    return render_template('messenger_test.html',
                         current_recipients=current_recipients)


# ==================== API 接口 ====================

@app.route('/api/status', methods=['GET'])
def get_status():
    """获取系统状态"""
    monitor = init_services()
    status = monitor.get_status()

    return jsonify({
        "success": True,
        "data": status
    })


@app.route('/api/config', methods=['GET'])
def get_config():
    """获取配置"""
    # 直接从配置文件加载（确保返回最新的配置）
    from src.monitor import MonitorConfig
    config_file = "config/monitor_config.json"
    config = MonitorConfig.load(config_file)

    return jsonify({
        "success": True,
        "data": config.to_dict()
    })


@app.route('/api/config', methods=['POST'])
def update_config():
    """更新配置

    Body: JSON 格式的配置参数
    {
        "rules": [...],
        "min_notify_interval": 10,
        "capture_interval": 30,
        ...
    }
    """
    monitor = init_services()

    try:
        data = request.get_json()

        # 更新配置（会自动保存到文件）
        monitor.update_config(**data)

        return jsonify({
            "success": True,
            "message": "配置已更新"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 400


@app.route('/api/messenger/test', methods=['POST'])
def test_messenger():
    """测试发送消息到指定收件人

    Body: JSON 格式
    {
        "recipient_id": "userid"
    }
    """
    monitor = init_services()
    messenger = monitor.messenger

    try:
        data = request.get_json()
        recipient_id = data.get('recipient_id', '').strip()

        if not recipient_id:
            return jsonify({
                "success": False,
                "message": "收件人ID不能为空"
            }), 400

        # 准备测试消息
        text_message = f"""Study Buddy Test Message

This is a test notification to verify the recipient ID is correct.

Consecutive Failures: 0

Analysis Results:
  test_field: test_value

Time: {time.strftime('%Y-%m-%d %H:%M:%S')}"""

        # 查找测试图片
        test_image = None
        captures_dir = PROJECT_ROOT / "data" / "captures"

        print(f"[DEBUG] captures_dir: {captures_dir}, exists: {captures_dir.exists()}")

        if captures_dir.exists():
            images = list(captures_dir.glob("*.jpg"))
            print(f"[DEBUG] 找到 {len(images)} 张图片")
            if images:
                # 使用最新的一张图片（按修改时间排序）
                test_image = str(sorted(images, key=lambda x: x.stat().st_mtime)[-1])
                print(f"[DEBUG] 选择的图片: {test_image}, exists: {Path(test_image).exists()}")

        if not test_image or not Path(test_image).exists():
            return jsonify({
                "success": False,
                "message": "没有可用的测试图片，请先运行监控生成截图"
            }), 400

        # 临时替换recipient进行测试
        from src.messenger import Message, MessageLevel

        # 获取企业微信适配器
        wechat_adapter = None
        for adapter in messenger.adapters:
            if adapter.platform_name == "wechat":
                wechat_adapter = adapter
                break

        if not wechat_adapter:
            return jsonify({
                "success": False,
                "message": "企业微信适配器未配置"
            }), 400

        # 发送文本消息
        print(f"[DEBUG] 准备发送文本消息到: {recipient_id}")
        text_success = wechat_adapter.send_text(text_message, recipient_id)
        print(f"[DEBUG] 文本消息发送结果: {text_success}")

        # 发送图片消息
        print(f"[DEBUG] 准备发送图片: {test_image}")
        image_success = wechat_adapter.send_image(test_image, recipient_id)
        print(f"[DEBUG] 图片消息发送结果: {image_success}")

        return jsonify({
            "success": True,
            "message": "测试完成",
            "data": {
                "text": text_success,
                "image": image_success,
                "recipient": recipient_id
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"测试失败: {str(e)}"
        }), 500


@app.route('/api/messenger/save_recipients', methods=['POST'])
def save_recipients():
    """保存收件人列表到 .env 文件

    Body: JSON 格式
    {
        "recipients": "RenYuan|xiaoyu"
    }
    """
    try:
        data = request.get_json()
        recipients = data.get('recipients', '').strip()

        if not recipients:
            return jsonify({
                "success": False,
                "message": "收件人列表不能为空"
            }), 400

        # 读取 .env 文件
        env_path = PROJECT_ROOT / '.env'
        if not env_path.exists():
            return jsonify({
                "success": False,
                "message": ".env 文件不存在"
            }), 400

        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 查找并修改 WECHAT_TOUSER 行
        found = False
        for i, line in enumerate(lines):
            if line.startswith('WECHAT_TOUSER='):
                lines[i] = f'WECHAT_TOUSER={recipients}\n'
                found = True
                break

        # 如果没找到，添加新行
        if not found:
            lines.append(f'WECHAT_TOUSER={recipients}\n')

        # 写回文件
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        # 更新环境变量（当前进程）
        os.environ['WECHAT_TOUSER'] = recipients

        # 重新初始化 messenger 服务
        global services, monitor_service
        if monitor_service:
            from src.messenger import create_messenger_service, MessengerConfig
            messenger_config = MessengerConfig(
                wechat_corpid=os.getenv("WECHAT_CORPID", ""),
                wechat_secret=os.getenv("WECHAT_SECRET", ""),
                wechat_agentid=os.getenv("WECHAT_AGENTID", ""),
                wechat_recipient=recipients,
                telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
                telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "")
            )
            new_messenger = create_messenger_service(messenger_config)
            monitor_service.messenger = new_messenger
            services['messenger'] = new_messenger

        return jsonify({
            "success": True,
            "message": "保存成功",
            "data": {
                "recipients": recipients
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"保存失败: {str(e)}"
        }), 500


@app.route('/api/monitor/start', methods=['POST'])
def start_monitor():
    """启动监控"""
    global preview_active, preview_start_time, preview_duration
    monitor = init_services()

    try:
        result = monitor.start_monitor()

        if result:
            # 获取预览时长
            duration = monitor.config.preview_duration

            # 只有启用预览时才激活
            if monitor.config.enable_preview and duration > 0:
                # 立即激活预览状态（monitor 的预览在后台线程中启动）
                with preview_lock:
                    preview_active = True
                    preview_start_time = time.time()
                    preview_duration = duration
                print(f"[预览] 预览已激活，持续 {duration} 秒")

                return jsonify({
                    "success": True,
                    "message": "监控已启动",
                    "preview_duration": duration
                })
            else:
                return jsonify({
                    "success": True,
                    "message": "监控已启动",
                    "preview_duration": 0
                })
        else:
            return jsonify({
                "success": False,
                "message": "监控已在运行"
            }), 400

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@app.route('/api/monitor/stop', methods=['POST'])
def stop_monitor():
    """停止监控"""
    global preview_active
    monitor = init_services()

    try:
        result = monitor.stop_monitor()

        if result:
            # 停止预览
            with preview_lock:
                preview_active = False

            return jsonify({
                "success": True,
                "message": "监控已停止"
            })
        else:
            return jsonify({
                "success": False,
                "message": "监控未在运行"
            }), 400

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@app.route('/api/records/today', methods=['GET'])
def get_today_records():
    """获取今天的检测记录"""
    import sqlite3
    from datetime import datetime

    # 获取今天的日期（YYYY-MM-DD 格式）
    today = datetime.now().strftime('%Y-%m-%d')

    conn = sqlite3.connect(str(PROJECT_ROOT / "data" / "detection_records.db"))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 查询今天的记录
    cursor.execute("""
        SELECT * FROM detection_records
        WHERE DATE(timestamp) = ?
        ORDER BY timestamp DESC
    """, (today,))

    rows = cursor.fetchall()
    records = [dict(row) for row in rows]

    conn.close()

    return jsonify({
        "success": True,
        "data": records,
        "count": len(records)
    })


@app.route('/api/records/recent', methods=['GET'])
def get_recent_records():
    """获取最近的检测记录"""
    monitor = init_services()

    # 获取最近 10 条记录
    import sqlite3
    conn = sqlite3.connect(str(PROJECT_ROOT / "data" / "detection_records.db"))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM detection_records
        ORDER BY timestamp DESC
        LIMIT 10
    """)

    rows = cursor.fetchall()
    records = [dict(row) for row in rows]

    conn.close()

    return jsonify({
        "success": True,
        "data": records,
        "count": len(records)
    })


@app.route('/image')
def serve_image():
    """提供检测图片"""
    from flask import send_file
    import os

    image_path = request.args.get('path')

    if not image_path:
        return "Missing path parameter", 400

    # 安全检查：确保路径在允许的目录内
    # 只允许访问 data/captures 目录下的图片
    if '..' in image_path or not image_path.startswith('data/captures/'):
        return "Invalid path", 403

    # 使用项目根目录构建完整路径
    full_path = PROJECT_ROOT / image_path

    if not os.path.exists(full_path):
        print(f"[图片] 文件不存在: {full_path}")
        return "Image not found", 404

    try:
        print(f"[图片] 提供文件: {full_path}")
        return send_file(full_path, mimetype='image/jpeg')
    except Exception as e:
        print(f"[图片] 错误: {e}")
        return f"Error: {str(e)}", 500


# ==================== 预览视频流 ====================

@app.route('/api/preview/status', methods=['GET'])
def get_preview_status():
    """获取预览状态"""
    global preview_active, preview_start_time, preview_duration

    with preview_lock:
        if not preview_active or preview_start_time is None:
            return jsonify({
                "success": True,
                "active": False,
                "remaining": 0
            })

        elapsed = time.time() - preview_start_time
        remaining = max(0, preview_duration - elapsed)

        # 如果超时，自动停止预览
        if elapsed >= preview_duration:
            preview_active = False
            return jsonify({
                "success": True,
                "active": False,
                "remaining": 0
            })

        return jsonify({
            "success": True,
            "active": True,
            "remaining": round(remaining, 1)
        })


def generate_preview_frames():
    """生成预览视频帧（MJPEG 流）

    注意：不启动新的预览，而是在 monitor 预览期间读取帧
    """
    global preview_active, preview_start_time, preview_duration

    monitor = init_services()
    camera_service = services.get("camera")

    if not camera_service:
        print("[视频流] camera_service 不存在")
        return

    # camera_service 是 CameraService，获取底层的 CameraSingleton
    camera_singleton = camera_service.camera if hasattr(camera_service, 'camera') else None
    if not camera_singleton:
        print("[视频流] camera_singleton 不存在")
        return

    print(f"[视频流] 开始生成帧，摄像头模式: {camera_singleton.get_mode()}")

    try:
        frame_count = 0
        while True:
            # 检查预览是否仍然活跃
            with preview_lock:
                if not preview_active or preview_start_time is None:
                    print(f"[视频流] 预览未激活，停止流")
                    break

                elapsed = time.time() - preview_start_time
                if elapsed >= preview_duration:
                    print(f"[视频流] 预览超时 ({elapsed:.1f}s >= {preview_duration}s)，停止流")
                    preview_active = False
                    break

            # 检查摄像头是否在 STREAM 模式（monitor 的预览模式）
            if camera_singleton.get_mode() != "stream":
                print(f"[视频流] 摄像头不在 stream 模式，当前模式: {camera_singleton.get_mode()}")
                time.sleep(0.5)
                continue

            # 直接从摄像头读取帧（不调用 start_preview，因为 monitor 已经启动了）
            frame_result = camera_singleton.read_frame()
            if frame_result is None:
                print("[视频流] 读取帧失败，frame_result is None")
                time.sleep(0.5)
                continue

            ret, frame = frame_result
            if not ret:
                print("[视频流] 读取帧失败，ret is False")
                time.sleep(0.5)
                continue

            frame_count += 1
            if frame_count % 30 == 0:  # 每 3 秒打印一次
                print(f"[视频流] 已发送 {frame_count} 帧")

            # 编码为 JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                print("[视频流] JPEG 编码失败")
                continue

            # 生成帧数据
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

            # 控制帧率（约 10 FPS）
            time.sleep(0.1)

    except Exception as e:
        print(f"[视频流] 异常: {e}")
        import traceback
        traceback.print_exc()


@app.route('/video_feed')
def video_feed():
    """视频流端点（仅预览阶段可用）"""
    global preview_active

    with preview_lock:
        if not preview_active:
            return Response(status=403, response="预览未激活")

    return Response(stream_with_context(generate_preview_frames()),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


# ==================== 错误处理 ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "message": "接口不存在"
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "message": "服务器内部错误"
    }), 500


# ==================== 启动命令 ====================

if __name__ == '__main__':
    # 初始化服务
    init_services()

    # 启动 Flask 应用
    app.run(host='0.0.0.0', port=5000, debug=True)
