"""
学习监工 - 主程序入口
监控孩子的学习状态并发送通知给家长
"""
import sys
import time
from pathlib import Path

# Windows 控制台 UTF-8 编码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

from core.config import config
from core.scheduler import Scheduler
from modules.vision import create_vision_module
from modules.im import create_im_module


class StudyMonitor:
    """学习监工主类"""

    def __init__(self):
        self.config = config
        self.vision_module = None
        self.im_module = None
        self.scheduler = None
        self.running = False

    def initialize(self) -> bool:
        """初始化所有模块"""
        print("=" * 50)
        print("学习监工系统启动中...")
        print("=" * 50)

        try:
            # 1. 初始化 Vision 模块
            print("\n[1/3] 初始化 Vision 模块...")
            self.vision_module = create_vision_module(self.config)
            camera_ready = self.vision_module["camera"].initialize()
            analyzer_ready = self.vision_module["analyzer"].initialize()

            if not (camera_ready and analyzer_ready):
                print("❌ Vision 模块初始化失败")
                return False
            print("✅ Vision 模块初始化成功")

            # 2. 初始化 IM 模块
            print("\n[2/3] 初始化 IM 模块...")
            self.im_module = create_im_module(self.config)
            if not self.im_module.initialize():
                print("⚠️  IM 模块初始化失败（将无法发送通知）")
            else:
                print("✅ IM 模块初始化成功")

            # 3. 初始化调度器
            print("\n[3/3] 初始化调度器...")
            self.scheduler = Scheduler(
                self.config,
                self.vision_module["analyzer"],
                self.im_module
            )
            if not self.scheduler.initialize():
                print("❌ 调度器初始化失败")
                return False
            print("✅ 调度器初始化成功")

            # 打印配置信息
            print("\n" + "=" * 50)
            print("配置信息:")
            print(f"  - Kimi 模型: {self.config.kimi.model}")
            print(f"  - 摄像头索引: {self.config.camera.camera_index}")
            print(f"  - 分辨率: {self.config.camera.resolution[0]}x{self.config.camera.resolution[1]}")
            print(f"  - 检查间隔: {self.config.scheduler.check_interval}秒")
            print(f"  - 提醒阈值: {self.config.scheduler.alert_threshold}次")
            print("=" * 50)

            return True

        except Exception as e:
            print(f"\n❌ 初始化失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run(self):
        """运行监控循环"""
        print("\n🚀 开始监控...")
        print("按 Ctrl+C 停止\n")

        self.running = True
        camera = self.vision_module["camera"]

        try:
            while self.running:
                # 捕获图像
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n[{timestamp}] 📸 捕获图像...")

                # 生成临时文件路径
                output_dir = Path("data/captures")
                output_dir.mkdir(parents=True, exist_ok=True)
                image_path = output_dir / f"capture_{int(time.time())}.jpg"

                try:
                    # 捕获图像（目前需要实际图片文件，TODO: 集成 OpenCV）
                    captured_path = camera.capture(str(image_path))

                    # 分析并决策
                    print(f"[{timestamp}] 🤖 分析图像...")
                    result = self.scheduler.analyze_and_decide(captured_path)

                    # 打印分析结果
                    analysis = result["analysis"]
                    decision = result["decision"]

                    print(f"\n分析结果:")
                    print(f"  - 在书桌前: {'是' if analysis.get('at_desk') else '否'}")
                    print(f"  - 正在玩耍: {'是' if analysis.get('is_playing') else '否'}")
                    print(f"  - 活动: {analysis.get('activity', '未知')}")
                    print(f"  - 坐姿: {analysis.get('posture', '未知')}")
                    print(f"  - 台灯: {'开启' if analysis.get('lamp_on') else '关闭'}")
                    print(f"  - 状态: {analysis.get('overall_status', '无')}")

                    # 打印决策结果
                    if decision["should_notify"]:
                        print(f"\n🔔 已发送通知: {decision['notify_reason']}")
                    else:
                        print(f"\n✓ 状态正常: {decision.get('notify_reason', '无需通知')}")

                except NotImplementedError:
                    print("\n⚠️  摄像头功能需要集成 OpenCV")
                    print("请在 data/captures/ 目录下放置测试图片，或集成 OpenCV")
                    print("退出程序...")
                    break

                except Exception as e:
                    print(f"\n❌ 处理失败: {e}")
                    import traceback
                    traceback.print_exc()

                # 等待下一次检查
                print(f"\n⏳ 等待 {self.config.scheduler.check_interval} 秒...")
                time.sleep(self.config.scheduler.check_interval)

        except KeyboardInterrupt:
            print("\n\n收到停止信号，正在退出...")

    def shutdown(self):
        """关闭所有模块"""
        print("\n" + "=" * 50)
        print("正在关闭系统...")

        if self.scheduler:
            self.scheduler.shutdown()

        if self.im_module:
            self.im_module.shutdown()

        if self.vision_module:
            self.vision_module["camera"].shutdown()
            self.vision_module["analyzer"].shutdown()

        print("系统已关闭")
        print("=" * 50)


def main():
    """主函数"""
    monitor = StudyMonitor()

    # 初始化
    if not monitor.initialize():
        print("\n初始化失败，退出程序")
        sys.exit(1)

    # 运行
    try:
        monitor.run()
    finally:
        monitor.shutdown()


if __name__ == "__main__":
    main()
