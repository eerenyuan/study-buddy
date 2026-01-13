"""
WebRTC 低延迟视频流服务器 - 基于官方实现
使用 MediaPlayer (FFmpeg) 而不是自定义 MediaStreamTrack
"""
import sys
import json
import asyncio
import platform
from pathlib import Path

# Windows 控制台 UTF-8 编码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer, MediaRelay


# 全局变量
pcs = set()
relay = None
webcam = None


async def index(request):
    """主页"""
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>WebRTC 摄像头流</title>
    <style>
    body {
        font-family: Arial, sans-serif;
        max-width: 1280px;
        margin: 0 auto;
        padding: 20px;
        background: #f5f5f5;
    }
    button {
        padding: 12px 24px;
        font-size: 16px;
        cursor: pointer;
        margin: 10px 5px;
    }
    video {
        width: 100%;
        max-width: 640px;
        background: #000;
        border-radius: 8px;
    }
    .info {
        background: white;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    </style>
</head>
<body>
    <div class="info">
        <h2>🎥 WebRTC 摄像头流（官方实现）</h2>
        <p>使用 aiortc 的 MediaPlayer（基于 FFmpeg）</p>
        <p id="status" style="color: #666;">等待启动...</p>
    </div>

    <button id="start" onclick="start()">启动视频流</button>
    <button id="stop" style="display: none" onclick="stop()">停止</button>

    <div>
        <video id="video" autoplay="true" playsinline="true"></video>
    </div>

    <script>
    console.log('页面已加载');
    var statusEl = document.getElementById('status');

    function setStatus(text, color) {
        statusEl.textContent = text;
        statusEl.style.color = color || '#666';
    }

    var pc = null;

    function negotiate() {
        console.log('开始 negotiate');
        setStatus('正在连接摄像头，首次启动可能需要 10-15 秒...', '#f39c12');

        pc.addTransceiver('video', { direction: 'recvonly' });
        return pc.createOffer().then((offer) => {
            console.log('Offer 已创建');
            return pc.setLocalDescription(offer);
        }).then(() => {
            console.log('等待 ICE 收集完成...');
            // wait for ICE gathering to complete
            return new Promise((resolve) => {
                if (pc.iceGatheringState === 'complete') {
                    resolve();
                } else {
                    const checkState = () => {
                        if (pc.iceGatheringState === 'complete') {
                            pc.removeEventListener('icegatheringstatechange', checkState);
                            resolve();
                        }
                    };
                    pc.addEventListener('icegatheringstatechange', checkState);
                }
            });
        }).then(() => {
            console.log('发送 offer 到服务器');
            setStatus('正在初始化摄像头（FFmpeg），请耐心等待...', '#e67e22');
            var offer = pc.localDescription;
            return fetch('/offer', {
                body: JSON.stringify({
                    sdp: offer.sdp,
                    type: offer.type,
                }),
                headers: {
                    'Content-Type': 'application/json'
                },
                method: 'POST'
            });
        }).then((response) => {
            console.log('收到服务器响应');
            setStatus('正在建立 WebRTC 连接...', '#3498db');
            return response.json();
        }).then((answer) => {
            console.log('设置远程描述');
            return pc.setRemoteDescription(answer);
        }).then(() => {
            console.log('WebRTC 连接建立完成');
            setStatus('✓ 视频流已连接', '#27ae60');
        }).catch((e) => {
            console.error('Error:', e);
            setStatus('✗ 连接失败: ' + e.message, '#e74c3c');
            alert('错误: ' + e);
        });
    }

    function start() {
        console.log('start() 被调用');
        var config = {
            sdpSemantics: 'unified-plan',
            iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
        };

        pc = new RTCPeerConnection(config);
        console.log('RTCPeerConnection 已创建');

        // connect video
        pc.addEventListener('track', (evt) => {
            console.log('收到 track:', evt.track.kind);
            if (evt.track.kind == 'video') {
                document.getElementById('video').srcObject = evt.streams[0];
                console.log('视频流已设置');
                setStatus('✓ 正在接收视频流', '#27ae60');
            }
        });

        pc.addEventListener('iceconnectionstatechange', () => {
            console.log('ICE状态:', pc.iceConnectionState);
            if (pc.iceConnectionState === 'connected') {
                setStatus('✓ ICE 连接成功', '#27ae60');
            } else if (pc.iceConnectionState === 'failed') {
                setStatus('✗ ICE 连接失败', '#e74c3c');
            }
        });

        document.getElementById('start').style.display = 'none';
        negotiate();
        document.getElementById('stop').style.display = 'inline-block';
    }

    function stop() {
        console.log('stop() 被调用');
        document.getElementById('stop').style.display = 'none';
        document.getElementById('start').style.display = 'inline-block';

        // close peer connection
        setTimeout(() => {
            if (pc) {
                pc.close();
                pc = null;
            }
        }, 500);
    }
    </script>
</body>
</html>
    """
    return web.Response(text=html, content_type="text/html")


async def offer(request):
    """处理 WebRTC offer"""
    global relay, webcam

    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print(f"连接状态: {pc.connectionState}")
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    # 如果摄像头还未初始化，立即初始化（但不等待完成）
    if relay is None:
        print("[WebRTC] 首次连接，初始化摄像头...")
        asyncio.create_task(init_webcam())

    # 等待摄像头初始化完成
    timeout = 15  # 最多等待15秒
    start_time = asyncio.get_event_loop().time()

    while relay is None:
        await asyncio.sleep(0.1)
        if asyncio.get_event_loop().time() - start_time > timeout:
            raise TimeoutError("摄像头初始化超时")

    # 订阅摄像头视频流
    video_track = relay.subscribe(webcam.video)

    # 添加到 peer connection
    pc.addTrack(video_track)

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps({
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        })
    )


async def init_webcam():
    """异步初始化摄像头"""
    global relay, webcam
    try:
        options = {"framerate": "30", "video_size": "640x480"}

        if platform.system() == "Darwin":  # macOS
            webcam = MediaPlayer("default:none", format="avfoundation", options=options)
        elif platform.system() == "Windows":  # Windows
            # 尝试常见的摄像头名称
            camera_names = [
                "video=Integrated Camera",
                "video=USB Camera",
                "video=HD Webcam",
                "video=Camera",
            ]

            for cam_name in camera_names:
                try:
                    print(f"[WebRTC] 尝试打开摄像头: {cam_name}")
                    webcam = MediaPlayer(cam_name, format="dshow", options=options)
                    print(f"[WebRTC] ✓ 成功使用摄像头: {cam_name}")
                    break
                except Exception as e:
                    print(f"[WebRTC] ✗ 失败: {cam_name}")
                    continue
            else:
                raise Exception("无法找到可用的摄像头")

        else:  # Linux
            webcam = MediaPlayer("/dev/video0", format="v4l2", options=options)

        relay = MediaRelay()
        print("[WebRTC] ✓ MediaPlayer 和 MediaRelay 初始化完成")
    except Exception as e:
        print(f"[WebRTC] ✗ 摄像头初始化失败: {e}")
        raise


async def on_shutdown(app):
    """关闭时清理资源"""
    # 关闭所有 peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()

    # 关闭摄像头
    global webcam
    if webcam is not None:
        webcam.video.stop()
        print("[WebRTC] 摄像头已关闭")


async def main():
    """主函数"""
    port = 8082  # 使用不同的端口避免冲突
    host = "0.0.0.0"

    print("=" * 60)
    print("WebRTC 低延迟视频流服务器（官方实现）")
    print("=" * 60)
    print(f"访问地址: http://localhost:{port}")
    print(f"操作系统: {platform.system()}")
    print(f"使用 MediaPlayer (FFmpeg)")
    print("=" * 60)

    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.router.add_post("/offer", offer)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)

    print(f"[WebRTC] 服务器已启动: http://{host}:{port}")

    try:
        await site.start()
        print(f"[WebRTC] 服务器运行中，按 Ctrl+C 停止")
        await asyncio.Future()
    except KeyboardInterrupt:
        print("\n[WebRTC] 收到停止信号，正在关闭...")
    finally:
        await runner.cleanup()


if __name__ == '__main__':
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[WebRTC] 服务器已停止")
