"""
摄像头测试模块 - 每10秒捕获一张截图
验证摄像头是否正常获取实时画面
"""
import sys
import cv2
import time
from pathlib import Path
from datetime import datetime

# Windows 控制台 UTF-8 编码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass


class CameraTester:
    """摄像头测试类"""

    def __init__(self, camera_index: int = 0, output_dir: str = "data/captures"):
        self.camera_index = camera_index
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cap = None

    def initialize(self) -> bool:
        """初始化摄像头"""
        print(f"[初始化] 尝试打开摄像头 (索引: {self.camera_index})...")

        self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            print(f"[错误] 无法打开摄像头 (索引: {self.camera_index})")
            return False

        # 获取摄像头实际分辨率
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(self.cap.get(cv2.CAP_PROP_FPS))

        print(f"[成功] 摄像头已打开")
        print(f"  - 分辨率: {width}x{height}")
        print(f"  - FPS: {fps}")

        return True

    def capture_frame(self, filename: str = None) -> str:
        """捕获一帧并保存

        Args:
            filename: 文件名，如果不指定则自动生成

        Returns:
            保存的文件路径
        """
        if not self.cap:
            raise Exception("摄像头未初始化")

        # 读取一帧
        ret, frame = self.cap.read()

        if not ret:
            raise Exception("无法从摄像头读取图像")

        # 生成文件名
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"camera_test_{timestamp}.jpg"

        filepath = self.output_dir / filename

        # 保存图像
        success = cv2.imwrite(str(filepath), frame)

        if not success:
            raise Exception(f"保存图像失败: {filepath}")

        # 获取图像信息
        height, width = frame.shape[:2]
        file_size = filepath.stat().st_size / 1024  # KB

        print(f"[捕获] {datetime.now().strftime('%H:%M:%S')} -> {filename}")
        print(f"  - 尺寸: {width}x{height}")
        print(f"  - 大小: {file_size:.1f} KB")
        print(f"  - 路径: {filepath}")

        return str(filepath)

    def shutdown(self):
        """关闭摄像头"""
        if self.cap:
            self.cap.release()
            print("[关闭] 摄像头已释放")

    def run_test(self, interval: int = 10, count: int = 5):
        """运行测试 - 定时捕获

        Args:
            interval: 捕获间隔（秒）
            count: 捕获次数
        """
        print("\n" + "=" * 60)
        print(f"摄像头测试开始 - 每 {interval} 秒捕获一次，共 {count} 次")
        print("按 Ctrl+C 可提前停止")
        print("=" * 60 + "\n")

        try:
            for i in range(count):
                print(f"\n[第 {i+1}/{count} 次]")

                # 捕获图像
                self.capture_frame()

                # 等待下一次捕获
                if i < count - 1:
                    print(f"\n等待 {interval} 秒...")
                    time.sleep(interval)

            print("\n" + "=" * 60)
            print("✅ 测试完成")
            print(f"图片保存在: {self.output_dir.absolute()}")
            print("=" * 60)

        except KeyboardInterrupt:
            print("\n\n[停止] 用户中断测试")
        except Exception as e:
            print(f"\n[错误] {e}")
            import traceback
            traceback.print_exc()


def main():
    """主函数"""
    # 检查摄像头索引
    camera_index = 0  # 默认摄像头

    # 创建测试器
    tester = CameraTester(camera_index=camera_index)

    # 初始化
    if not tester.initialize():
        print("\n初始化失败，请检查:")
        print("1. 摄像头是否连接")
        print("2. 摄像头是否被其他程序占用")
        print("3. 尝试修改 camera_index 参数 (0, 1, 2...)")
        return

    # 运行测试：每10秒捕获一次，共5次
    try:
        tester.run_test(interval=10, count=5)
    finally:
        tester.shutdown()


if __name__ == "__main__":
    main()
