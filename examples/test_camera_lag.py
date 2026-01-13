"""
摄像头滞后测试
验证两次长时间间隔捕获是否能获取实时画面
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


def test_camera_lag():
    """测试摄像头是否有滞后"""
    print("=" * 60)
    print("摄像头滞后测试")
    print("=" * 60)
    print("\n测试说明:")
    print("1. 连续捕获3张照片，每次间隔30秒")
    print("2. 每次捕获后请移动摄像头画面（用手遮挡或移动位置）")
    print("3. 检查捕获的照片是否是实时画面\n")

    input("准备好后按回车开始...")

    # 打开摄像头
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ 无法打开摄像头")
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"\n摄像头已打开: {width}x{height}")

    output_dir = Path("data/captures")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        for i in range(3):
            print(f"\n{'='*60}")
            print(f"[第 {i+1}/3 次] {datetime.now().strftime('%H:%M:%S')}")

            if i > 0:
                print(f"请移动摄像头或用手遮挡画面，然后等待...")
                print("倒计时:", end=" ")
                for count in range(30, 0, -5):
                    print(f"{count}", end=" ")
                    time.sleep(5)
                print()

            # 清空缓冲区（重要！）
            print("清空缓冲区...", end=" ")
            for _ in range(5):
                cap.read()
            print("完成")

            # 读取最新帧
            print("捕获图像...", end=" ")
            ret, frame = cap.read()
            if not ret:
                print("❌ 失败")
                continue

            # 保存图像
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = output_dir / f"lag_test_{timestamp}.jpg"
            cv2.imwrite(str(filename), frame)
            print(f"✓ 完成")
            print(f"文件: {filename.name}")

            # 获取文件信息
            file_size = filename.stat().st_size / 1024
            print(f"大小: {file_size:.1f} KB")

        print(f"\n{'='*60}")
        print("✅ 测试完成")
        print(f"\n请检查以下图片，确认画面是否有滞后:")
        print(f"目录: {output_dir.absolute()}")
        print("\n如果每次捕获的画面都不同且反映当时的动作，说明无滞后")
        print("如果画面相同或延迟，说明仍有滞后问题")

    finally:
        cap.release()
        print("\n摄像头已关闭")


if __name__ == "__main__":
    test_camera_lag()
