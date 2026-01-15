// 主页 JavaScript

let previewTimer = null;  // 预览定时器

// 刷新状态
async function refreshStatus() {
    try {
        const response = await fetch('/api/status');
        const result = await response.json();

        if (result.success) {
            const status = result.data;

            // 更新监控状态
            const monitoringStatus = document.getElementById('monitoring-status');
            monitoringStatus.innerHTML = status.is_monitoring
                ? '<span class="badge badge-success">运行中</span>'
                : '<span class="badge badge-secondary">已停止</span>';

            // 更新连续失败次数
            document.getElementById('consecutive-failures').textContent = status.consecutive_failures;
            document.getElementById('fail-limit').textContent = status.notify_manager.consecutive_fail_limit;

            // 更新按钮状态
            document.getElementById('btn-start').disabled = status.is_monitoring;
            document.getElementById('btn-stop').disabled = !status.is_monitoring;
        }
    } catch (error) {
        console.error('刷新状态失败:', error);
        alert('刷新状态失败: ' + error.message);
    }
}

// 检查预览状态
async function checkPreviewStatus() {
    try {
        const response = await fetch('/api/preview/status');
        const result = await response.json();

        console.log('[预览状态]', result);

        if (result.success) {
            const previewContainer = document.getElementById('preview-container');
            const videoFeed = document.getElementById('video-feed');
            const countdown = document.getElementById('preview-countdown');

            if (result.active) {
                // 预览活跃中
                console.log('[预览] 活跃中，剩余时间:', result.remaining);
                console.log('[预览] 当前视频 src:', videoFeed.src);

                previewContainer.style.display = 'block';
                videoFeed.style.display = 'block';
                document.getElementById('video-error').style.display = 'none';

                // 更新倒计时
                countdown.textContent = `(${result.remaining}秒后自动关闭)`;

                // 每次都强制重新加载视频流
                const videoUrl = '/video_feed?t=' + new Date().getTime();
                console.log('[预览] 启动视频流:', videoUrl);

                // 先清除旧的事件监听器
                videoFeed.onload = null;
                videoFeed.onerror = null;

                // 设置新的 src
                videoFeed.src = videoUrl;

                // 监听视频加载事件
                videoFeed.onload = () => console.log('[预览] 视频加载成功');
                videoFeed.onerror = (e) => console.error('[预览] 视频加载失败:', e);
            } else {
                // 预览已结束
                if (previewContainer.style.display !== 'none') {
                    console.log('[预览] 已结束');
                    // 停止视频流
                    videoFeed.src = '';
                    previewContainer.style.display = 'none';

                    // 清除定时器
                    if (previewTimer) {
                        clearInterval(previewTimer);
                        previewTimer = null;
                    }

                    // 刷新状态
                    refreshStatus();
                }
            }
        }
    } catch (error) {
        console.error('[预览] 检查预览状态失败:', error);
    }
}

// 启动监控
async function startMonitor() {
    try {
        console.log('[启动监控] 开始启动...');
        const response = await fetch('/api/monitor/start', {
            method: 'POST'
        });
        const result = await response.json();

        console.log('[启动监控] 响应:', result);

        if (result.success) {
            alert(result.message);

            // 显示预览
            if (result.preview_duration && result.preview_duration > 0) {
                console.log('[启动监控] 预览时长:', result.preview_duration);
                // 延迟 1 秒后开始检查预览状态（给 monitor 预览启动的时间）
                setTimeout(() => {
                    console.log('[启动监控] 开始检查预览状态');
                    checkPreviewStatus();

                    // 启动定时器检查预览状态（每秒）
                    if (previewTimer) {
                        clearInterval(previewTimer);
                    }
                    previewTimer = setInterval(checkPreviewStatus, 1000);
                }, 1000);
            } else {
                console.log('[启动监控] 无预览，直接刷新状态');
                refreshStatus();
            }
        } else {
            alert('启动失败: ' + result.message);
        }
    } catch (error) {
        console.error('启动监控失败:', error);
        alert('启动监控失败: ' + error.message);
    }
}

// 停止监控
async function stopMonitor() {
    try {
        const response = await fetch('/api/monitor/stop', {
            method: 'POST'
        });
        const result = await response.json();

        if (result.success) {
            alert(result.message);

            // 隐藏预览
            const previewContainer = document.getElementById('preview-container');
            const videoFeed = document.getElementById('video-feed');
            videoFeed.src = '';
            previewContainer.style.display = 'none';

            // 清除定时器
            if (previewTimer) {
                clearInterval(previewTimer);
                previewTimer = null;
            }

            refreshStatus();
        } else {
            alert('停止失败: ' + result.message);
        }
    } catch (error) {
        console.error('停止监控失败:', error);
        alert('停止监控失败: ' + error.message);
    }
}

// 绑定事件
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('btn-start').addEventListener('click', startMonitor);
    document.getElementById('btn-stop').addEventListener('click', stopMonitor);
    document.getElementById('btn-refresh').addEventListener('click', refreshStatus);

    // 定时刷新状态（每 5 秒）
    setInterval(refreshStatus, 5000);
});
