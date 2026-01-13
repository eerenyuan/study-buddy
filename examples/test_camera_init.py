"""
测试摄像头初始化首帧问题
验证重新打开摄像头是否会返回相同的旧帧
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


def test_camera_reopen():
    """测试重新打开摄像头的行为"""
    print("=" * 60)
    print("摄像头重新打开测试")
    print("=" * 60)

    output_dir = Path("data/captures")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n测试流程:")
    print("1. 打开摄像头，捕获3帧（不丢弃）")
    print("2. 关闭摄像头，等待5秒")
    print("3. 重新打开，捕获3帧")
    print("4. 对比所有捕获的帧\n")

    input("请在摄像头前移动或用手遮挡，然后按回车开始...")

    results = []

    # 第一次打开
    print(f"\n{'='*60}")
    print("[第一次打开摄像头]")
    print(f"时间: {datetime.now().strftime('%H:%M:%S')}")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ 无法打开摄像头")
        return

    try:
        for i in range(3):
            ret, frame = cap.read()
            if ret:
                filename = output_dir / f"test1_frame{i}_{int(time.time())}.jpg"
                cv2.imwrite(str(filename), frame)
                file_size = filename.stat().st_size / 1024
                print(f"  帧{i}: 保存为 {filename.name} ({file_size:.1f} KB)")
                results.append({
                    'session': 1,
                    'frame': i,
                    'file': filename,
                    'size': file_size,
                    'time': datetime.now()
                })
            time.sleep(0.5)
    finally:
        cap.release()
        print("摄像头已关闭")

    # 等待
    print("\n请移动摄像头或用手遮挡画面...")
    print("倒计时: ", end="")
    for count in range(5, 0, -1):
        print(f"{count} ", end="", flush=True)
        time.sleep(1)
    print()

    # 第二次打开
    print(f"\n{'='*60}")
    print("[第二次打开摄像头]")
    print(f"时间: {datetime.now().strftime('%H:%M:%S')}")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ 无法打开摄像头")
        return

    try:
        for i in range(3):
            ret, frame = cap.read()
            if ret:
                filename = output_dir / f"test2_frame{i}_{int(time.time())}.jpg"
                cv2.imwrite(str(filename), frame)
                file_size = filename.stat().st_size / 1024
                print(f"  帧{i}: 保存为 {filename.name} ({file_size:.1f} KB)")
                results.append({
                    'session': 2,
                    'frame': i,
                    'file': filename,
                    'size': file_size,
                    'time': datetime.now()
                })
            time.sleep(0.5)
    finally:
        cap.release()
        print("摄像头已关闭")

    # 分析结果
    print(f"\n{'='*60}")
    print("测试结果分析")
    print(f"{'='*60}")

    print("\n保存的文件:")
    for r in results:
        print(f"  [{r['session']}-帧{r['frame']}] {r['file'].name} ({r['size']:.1f} KB)")

    print("\n请手动对比图片:")
    print(f"  目录: {output_dir.absolute()}")
    print("\n检查项:")
    print("  1. test1_frame0 和 test2_frame0 是否相同？")
    print("     如果相同，说明摄像头会返回缓存的旧帧")
    print("  2. 同一次打开的3帧是否相同？")
    print("     如果相同，说明摄像头没有及时更新")
    print("  3. 文件大小是否有显著差异？")
    print("     大小差异通常表示画面内容不同")

    # 简单的文件大小对比
    sizes = [r['size'] for r in results]
    if abs(sizes[0] - sizes[3]) < 0.1:  # 第一次的帧0 vs 第二次的帧0
        print("\n⚠️  警告: test1_frame0 和 test2_frame0 大小几乎相同")
        print("   这表明摄像头重新打开后返回了相同的旧帧！")
    else:
        print("\n✓ test1_frame0 和 test2_frame0 大小不同，画面应该是实时的")


if __name__ == "__main__":
    test_camera_reopen()
