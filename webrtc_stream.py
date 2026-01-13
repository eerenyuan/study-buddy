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
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaPlayer
from av import VideoFrame
import tempfile
import os

# 全局变量保持 track 的强引用，防止被 GC 回收
_global_tracks = []


# 备用方案：保持使用自定义 Track，但改进引用管理
class CameraStreamTrack(MediaStreamTrack):
    """自定义摄像头视频流 Track"""

    kind = "video"

    # 类级别的摄像头实例，所有 track 共享
    _shared_cap = None
    _cap_lock = asyncio.Lock()

    def __init__(self, camera_index: int = 0, width: int = 640, height: int = 480):
        super().__init__()
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.pts = 0  # 时间戳
        # 注意：不在 __init__ 中打开摄像头

    @classmethod
    async def ensure_camera(cls, camera_index: int, width: int, height: int):
        """确保摄像头已打开（类方法）"""
        async with cls._cap_lock:
            if cls._shared_cap is None or not cls._shared_cap.isOpened():
                print("[WebRTC] 初始化共享摄像头...")
                cls._shared_cap = cv2.VideoCapture(camera_index)

                if not cls._shared_cap.isOpened():
                    print(f"[WebRTC] 无法打开摄像头 (索引: {camera_index})")
                    return False

                # 设置摄像头参数
                cls._shared_cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cls._shared_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                cls._shared_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 低延迟

                actual_width = int(cls._shared_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(cls._shared_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                print(f"[WebRTC] 摄像头初始化成功: {actual_width}x{actual_height}")
        return True

    async def recv(self):
        """接收下一帧"""
        try:
            if self.pts == 0:
                print("[WebRTC] ========== recv() 首次被调用 ==========")

            # 确保摄像头已打开
            await self.ensure_camera(self.camera_index, self.width, self.height)

            if self._shared_cap is None or not self._shared_cap.isOpened():
                raise RuntimeError("摄像头未初始化")

            # 读取帧
            ret, frame = self._shared_cap.read()
            if not ret:
                print("[WebRTC] 读取帧失败")
                raise RuntimeError("无法读取摄像头帧")

            # 转换颜色空间 BGR -> RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # 创建 VideoFrame
            video_frame = VideoFrame.from_ndarray(frame, format="rgb24")
            video_frame.pts = self.pts
            video_frame.time_base = "1/90000"  # 90kHz 时钟

            self.pts += 3000  # 33.33ms @ 90kHz (约30fps)

            # 每30帧输出一次日志
            if self.pts % 90000 == 0:  # 每秒一次
                print(f"[WebRTC] 发送帧: {video_frame.pts}, pts={video_frame.pts}")

            if self.pts == 3000:  # 第二帧
                print("[WebRTC] ========== recv() 正常工作 ==========")

            return video_frame
        except Exception as e:
            print(f"[WebRTC] recv() 异常: {e}")
            import traceback
            traceback.print_exc()
            raise

    def stop(self):
        """stop() 方法不再关闭摄像头，因为它是共享的"""
        print("[WebRTC] stop() 被调用，但不关闭共享摄像头")
        pass

    @classmethod
    def close_camera(cls):
        """关闭共享摄像头（类方法）"""
        if cls._shared_cap:
            cls._shared_cap.release()
            cls._shared_cap = None
            print("[WebRTC] 共享摄像头已关闭")


class WebRTCStreamServer:
    """WebRTC 视频流服务器"""

    def __init__(self, camera_index: int = 0, width: int = 640, height: int = 480):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.pc = None
        self.camera_track = None  # 将在 offer 中创建

    async def offer(self, request):
        """处理 WebRTC offer"""
        print("[WebRTC] ========== offer() 被调用 ==========")
        params = await request.json()
        print(f"[WebRTC] 收到 offer type: {params['type']}")
        print(f"[WebRTC] offer SDP 长度: {len(params['sdp'])} 字符")
        # 检查 SDP 中是否有视频描述
        if 'm=video' in params['sdp']:
            print("[WebRTC] ✓ SDP 包含视频描述")
        else:
            print("[WebRTC] ✗ SDP 不包含视频描述！")

        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

        from aiortc import RTCPeerConnection
        self.pc = RTCPeerConnection()

        # 创建摄像头 track
        if self.camera_track is None:
            print("[WebRTC] 创建新的 CameraStreamTrack")
            self.camera_track = CameraStreamTrack(
                camera_index=self.camera_index,
                width=self.width,
                height=self.height
            )
            # 添加到全局列表以保持强引用（防止 GC）
            _global_tracks.append(self.camera_track)
        else:
            print("[WebRTC] 复用已有的 CameraStreamTrack")

        # 添加 track 到连接
        print("[WebRTC] 添加 track 到 RTCPeerConnection")
        self.pc.addTrack(self.camera_track)
        # 也将 pc 添加到全局列表
        _global_tracks.append(self.pc)

        # 设置远程描述
        print("[WebRTC] 设置远程描述")
        await self.pc.setRemoteDescription(offer)

        # 创建 answer
        print("[WebRTC] 创建 answer")
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)

        print("[WebRTC] ========== offer() 完成 ==========")

        # 监听连接状态
        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            print(f"[WebRTC] 连接状态变更: {self.pc.connectionState}")
            if self.pc.connectionState == "connected":
                print("[WebRTC] 连接已建立，应该开始传输数据")

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

                // 监听 incoming track
                pc.ontrack = (event) => {
                    console.log('[WebRTC] 收到视频流');
                    console.log('[WebRTC] track kind:', event.track.kind);
                    console.log('[WebRTC] streams:', event.streams.length);
                    console.log('[WebRTC] stream tracks:', event.streams[0]?.getTracks().length);

                    if (event.track.kind === 'video') {
                        video.srcObject = event.streams[0];

                        // 检查视频元素
                        video.addEventListener('loadedmetadata', () => {
                            console.log('[WebRTC] 视频尺寸:', video.videoWidth, 'x', video.videoHeight);
                        });

                        video.addEventListener('playing', () => {
                            console.log('[WebRTC] 视频开始播放');
                        });

                        video.play()
                            .then(() => {
                                console.log('[WebRTC] 视频播放成功');
                                startTime = Date.now();
                                updateStats();
                            })
                            .catch(err => {
                                console.error('[WebRTC] 视频播放失败:', err);
                            });
                    }
                };

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
                        stats.textContent = '已连接';
                        btnStart.disabled = true;
                        btnStop.disabled = false;
                    } else if (pc.iceConnectionState === 'failed') {
                        stats.textContent = '连接失败';
                        stop();
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

                stats.textContent = '等待视频流...';

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
        # 关闭共享摄像头
        CameraStreamTrack.close_camera()

        # 清理全局引用
        global _global_tracks
        for item in _global_tracks:
            if hasattr(item, 'close'):
                await item.close()
        _global_tracks.clear()

        if self.pc:
            await self.pc.close()


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
