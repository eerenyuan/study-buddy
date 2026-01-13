"""
WebRTC 低延迟视频流服务器
使用 aiortc 实现 100-300ms 延迟的实时视频流
"""
import sys
import json
import asyncio
import cv2
import time
from pathlib import Path
from typing import Optional

# Windows 控制台 UTF-8 编码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer
from av import VideoFrame


class WebRTCStreamServer:
    """WebRTC 视频流服务器"""

    def __init__(self, camera_index: int = 0, width: int = 640, height: int = 480):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.pc = None
        self.cap = None

    async def camera_track_generator(self):
        """生成器：从摄像头读取帧"""
        print("[WebRTC] 初始化摄像头...")
        self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            print(f"[WebRTC] 无法打开摄像头 (索引: {self.camera_index})")
            return

        # 设置摄像头参数
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 低延迟

        actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[WebRTC] 摄像头初始化成功: {actual_width}x{actual_height}")

        frame_time = 0
        frame_count = 0
        fps_target = 30
        frame_duration = 1.0 / fps_target

        try:
            while True:
                start_time = time.time()

                # 读取帧
                ret, frame = self.cap.read()
                if not ret:
                    print("[WebRTC] 读取帧失败，尝试重新打开摄像头...")
                    self.cap.release()
                    self.cap = cv2.VideoCapture(self.camera_index)
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    continue

                # 转换颜色空间 BGR -> RGB
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # 创建 VideoFrame
                video_frame = VideoFrame.from_ndarray(frame, format="rgb24")
                video_frame.pts = int(frame_time * 90000)  # 90kHz 时钟
                video_frame.time_base = "1/90000"

                yield video_frame

                frame_time += frame_duration
                frame_count += 1

                # 每30帧输出一次
                if frame_count % 30 == 0:
                    elapsed = time.time() - start_time
                    print(f"[WebRTC] 已发送 {frame_count} 帧")

                # 控制帧率
                elapsed = time.time() - start_time
                sleep_time = frame_duration - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        except Exception as e:
            print(f"[WebRTC] 摄像头错误: {e}")
        finally:
            if self.cap:
                self.cap.release()
                print("[WebRTC] 摄像头已关闭")

    async def offer(self, request):
        """处理 WebRTC offer"""
        params = await request.json()
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

        from aiortc import RTCPeerConnection
        self.pc = RTCPeerConnection()
        self.pc.addTrack(self.camera_track_generator())

        # 设置远程描述
        await self.pc.setRemoteDescription(offer)

        # 创建 answer
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)

        return web.Response(
            content_type="application/json",
            text=json.dumps({
                "sdp": self.pc.localDescription.sdp,
                "type": self.pc.localDescription.type
            })
        )

    async def index(self, request):
        """主页"""
        return web.Response(
            text=self.get_html_page(),
            content_type="text/html"
        )

    def get_html_page(self):
        """生成 HTML 页面"""
        return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WebRTC 低延迟视频流</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0f1419;
            color: #fff;
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .header h1 {
            font-size: 28px;
            margin-bottom: 10px;
        }
        .stats {
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
            font-family: monospace;
            font-size: 14px;
        }
        .video-container {
            background: #000;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            margin-bottom: 20px;
        }
        #video {
            width: 100%;
            height: auto;
            display: block;
            background: #000;
        }
        .controls {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            margin-bottom: 20px;
        }
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
        .info-panel {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .info-panel h2 {
            color: #58a6ff;
            margin-bottom: 15px;
            font-size: 18px;
        }
        .info-item {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #30363d;
        }
        .info-item:last-child { border-bottom: none; }
        .info-label { color: #8b949e; }
        .info-value { color: #c9d1d9; font-weight: 600; }
        .back-link {
            display: inline-block;
            color: #58a6ff;
            text-decoration: none;
            font-weight: 600;
        }
        .back-link:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎥 WebRTC 低延迟视频流</h1>
            <p>超低延迟实时摄像头画面 (预期延迟: 100-300ms)</p>
            <div class="stats" id="stats">等待连接...</div>
        </div>

        <div class="video-container">
            <video id="video" autoplay playsinline muted></video>
        </div>

        <div class="controls">
            <button class="btn btn-start" id="btnStart" onclick="start()">启动视频流</button>
            <button class="btn btn-stop" id="btnStop" onclick="stop()" disabled>停止视频流</button>
        </div>

        <div class="info-panel">
            <h2>📊 技术信息</h2>
            <div class="info-item">
                <span class="info-label">技术</span>
                <span class="info-value">WebRTC (aiortc)</span>
            </div>
            <div class="info-item">
                <span class="info-label">分辨率</span>
                <span class="info-value">640 x 480</span>
            </div>
            <div class="info-item">
                <span class="info-label">目标帧率</span>
                <span class="info-value">30 FPS</span>
            </div>
            <div class="info-item">
                <span class="info-label">预期延迟</span>
                <span class="info-value">100-300ms</span>
            </div>
            <div class="info-item">
                <span class="info-label">优势</span>
                <span class="info-value">UDP传输，硬件加速，智能缓冲</span>
            </div>
        </div>

        <a href="/" class="back-link">← 返回主页面</a>
    </div>

    <script>
        const video = document.getElementById('video');
        const btnStart = document.getElementById('btnStart');
        const btnStop = document.getElementById('btnStop');
        const stats = document.getElementById('stats');
        let pc = null;
        let startTime = null;
        let frameCount = 0;

        async function start() {
            try {
                stats.textContent = '正在连接...';

                // 创建 RTCPeerConnection
                pc = new RTCPeerConnection({
                    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
                    iceTransportPolicy: 'all'
                });

                // 添加 transceiver
                pc.addTransceiver('video', { direction: 'recvonly' });

                // 监听 candidates
                pc.onicecandidate = (event) => {
                    if (event.candidate === null) {
                        console.log('[WebRTC] ICE 收集完成');
                    }
                };

                // 监听连接状态
                pc.oniceconnectionstatechange = () => {
                    console.log('[WebRTC] ICE 状态:', pc.iceConnectionState);
                    if (pc.iceConnectionState === 'connected') {
                        startTime = Date.now();
                        updateStats();
                    }
                };

                pc.onconnectionstatechange = () => {
                    console.log('[WebRTC] 连接状态:', pc.connectionState);
                    if (pc.connectionState === 'failed') {
                        stats.textContent = '连接失败';
                        stop();
                    }
                };

                // 创建 offer
                const offer = await pc.createOffer();
                await pc.setLocalDescription(offer);

                // 发送 offer 到服务器
                const response = await fetch('/offer', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        sdp: pc.localDescription.sdp,
                        type: pc.localDescription.type
                    })
                });

                if (!response.ok) {
                    throw new Error('服务器返回错误: ' + response.status);
                }

                const answer = await response.json();
                await pc.setRemoteDescription(new RTCSessionDescription(answer));

                video.srcObject = await pc.recv();
                await video.play();

                stats.textContent = '已连接';
                btnStart.disabled = true;
                btnStop.disabled = false;

                // 监控视频统计
                video.addEventListener('play', () => {
                    startTime = Date.now();
                    updateStats();
                });

            } catch (error) {
                console.error('[WebRTC] 错误:', error);
                stats.textContent = '错误: ' + error.message;
                stop();
            }
        }

        async function stop() {
            try {
                if (pc) {
                    pc.close();
                    pc = null;
                }

                if (video.srcObject) {
                    video.srcObject.getTracks().forEach(track => track.stop());
                    video.srcObject = null;
                }

                stats.textContent = '已停止';
                btnStart.disabled = false;
                btnStop.disabled = true;

            } catch (error) {
                console.error('[WebRTC] 停止错误:', error);
            }
        }

        function updateStats() {
            if (!startTime || !video.srcObject) return;

            const elapsed = (Date.now() - startTime) / 1000;
            const stream = video.srcObject;
            const track = stream.getVideoTracks()[0];

            if (track && 'getStats' in track) {
                track.getStats().then(stats => {
                    stats.forEach(report => {
                        if (report.type === 'inbound-rtp' && 'framesReceived' in report) {
                            const fps = Math.round(report.framesReceived / elapsed);
                            const currentDelay = report.currentRoundTripTime || 0;
                            document.getElementById('stats').textContent =
                                `已运行: ${elapsed.toFixed(1)}秒 | 帧数: ${report.framesReceived} | FPS: ${fps} | 延迟: ${currentDelay}ms`;
                        }
                    });
                });
            }

            requestAnimationFrame(updateStats);
        }
    </script>
</body>
</html>
"""

    async def on_shutdown(self, app):
        """关闭时清理资源"""
        print("[WebRTC] 正在关闭服务器...")
        if self.cap:
            self.cap.release()


async def main():
    """主函数"""
    port = 8081
    camera_index = 0

    print("=" * 60)
    print("WebRTC 低延迟视频流服务器")
    print("=" * 60)
    print(f"访问地址: http://localhost:{port}")
    print(f"摄像头索引: {camera_index}")
    print("=" * 60)

    server = WebRTCStreamServer(camera_index=camera_index)
    app = web.Application()
    app.router.add_get('/', server.index)
    app.router.add_post('/offer', server.offer)
    app.on_shutdown.append(server.on_shutdown)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)

    print(f"[WebRTC] 服务器已启动: http://0.0.0.0:{port}")

    try:
        await site.start()
        print(f"[WebRTC] 服务器运行中，按 Ctrl+C 停止")
        # 保持运行
        await asyncio.Future()
    except KeyboardInterrupt:
        print("\n[WebRTC] 收到停止信号，正在关闭...")
    finally:
        await runner.cleanup()


if __name__ == '__main__':
    try:
        # Windows 下使用 ProactorEventLoop
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[WebRTC] 服务器已停止")
