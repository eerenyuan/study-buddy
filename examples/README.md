# StudyBuddy 示例程序

这个目录包含了一些开发和测试时使用的示例程序，可以帮助你了解系统的工作原理。

## 📁 文件说明

### 主程序

**main.py** - 命令行版本的主程序
- 使用 `.env` 文件中的配置运行
- 固定的监控间隔和规则
- 适合简单测试或后台服务运行

```bash
# 使用方法
cd study-buddy
python main.py
```

**注意**：推荐使用 `web_server.py`，它提供了更友好的 Web 界面。

---

## 🧪 测试程序

### test_setup.py - 模块初始化测试

测试所有模块是否能正常初始化：
- Vision 模块（摄像头 + 分析器）
- IM 模块（企业微信通知）
- Scheduler（调度中心）

```bash
python test_setup.py
```

---

### test_camera.py - 摄像头基础测试

测试摄像头是否正常工作：
- 打开摄像头（索引 0）
- 每 10 秒捕获一张照片
- 保存到 `data/captures/` 目录
- 共捕获 5 张照片

```bash
python test_camera.py
```

**用途**：验证摄像头驱动和权限是否正常。

---

### test_camera_lag.py - 摄像头延迟测试

测试摄像头是否有延迟问题：
- 连续捕获 3 张照片
- 每次间隔 5 秒
- 要求在间隔期移动摄像头画面
- 检查捕获的图片是否实时更新

```bash
python test_camera_lag.py
```

**用途**：验证 OpenCV 缓冲区清理是否有效。

---

### test_camera_init.py - 摄像头初始化测试

测试摄像头重新打开的行为：
- 打开摄像头，捕获 3 帧
- 关闭摄像头，等待 5 秒
- 重新打开，再捕获 3 帧
- 检查是否有缓存的旧帧

```bash
python test_camera_init.py
```

**用途**：诊断摄像头驱动问题。

---

### test_full_cycle.py - 完整流程测试

测试一次完整的监控流程：
1. 初始化 Vision 模块
2. 初始化 IM 模块
3. 初始化 Scheduler
4. 捕获一张照片
5. 调用 Kimi Vision API 分析
6. 发送通知到企业微信

```bash
python test_full_cycle.py
```

**用途**：验证整个系统是否正常工作。

---

## 🚀 快速测试指南

### 1. 测试摄像头

```bash
python test_camera.py
```

如果成功，你会在 `data/captures/` 看到 5 张照片。

### 2. 测试完整流程

```bash
python test_full_cycle.py
```

如果成功，你会：
- 看到摄像头捕获
- 看到 Kimi 分析结果
- 在企业微信收到测试通知

### 3. 测试模块初始化

```bash
python test_setup.py
```

应该看到所有模块初始化成功的消息。

---

## ⚠️ 注意事项

1. **环境变量**：所有测试都需要 `.env` 文件配置
2. **摄像头权限**：确保程序有访问摄像头的权限
3. **网络连接**：测试需要连接 Kimi API 和企业微信 API
4. **企业微信**：测试会发送真实消息，注意不要打扰

---

## 🔧 调试建议

如果遇到问题，按以下顺序测试：

1. **test_setup.py** - 检查模块是否正常加载
2. **test_camera.py** - 检查摄像头是否正常
3. **test_full_cycle.py** - 检查完整流程

这样可以帮助定位问题所在。

---

## 📝 开发者说明

这些测试程序主要用于：
- ✅ 开发时验证功能
- ✅ 排查问题和调试
- ✅ 学习系统架构
- ✅ 了解各个模块的用法

**不建议**：
- ❌ 作为生产环境使用
- ❌ 长期运行监控

生产环境请使用 `web_server.py`。
