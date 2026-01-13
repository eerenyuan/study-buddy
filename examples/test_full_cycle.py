"""
完整流程测试 - 单次运行
捕获 -> 分析 -> 通知
"""
import sys
from pathlib import Path

# Windows 控制台 UTF-8 编码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.config import config
from core.scheduler import Scheduler
from modules.vision import create_vision_module
from modules.im import create_im_module
import time


def test_full_cycle():
    """测试完整流程"""
    print("=" * 60)
    print("完整流程测试 - 单次运行")
    print("=" * 60)

    # 初始化模块
    print("\n[1/3] 初始化 Vision 模块...")
    vision_module = create_vision_module(config)
    if not vision_module["camera"].initialize():
        print("❌ 摄像头初始化失败")
        return

    print("\n[2/3] 初始化 IM 模块...")
    im_module = create_im_module(config)
    im_module.initialize()

    print("\n[3/3] 初始化调度器...")
    scheduler = Scheduler(config, vision_module["analyzer"], im_module)
    scheduler.initialize()

    # 执行一次完整流程
    print("\n" + "=" * 60)
    print("开始执行完整流程...")
    print("=" * 60)

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{timestamp}] 📸 第1步：捕获图像...")

    # 捕获图像
    output_dir = Path("data/captures")
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / f"test_{int(time.time())}.jpg"

    try:
        captured_path = vision_module["camera"].capture(str(image_path))
        print(f"✓ 图像已保存: {captured_path}")

    except Exception as e:
        print(f"❌ 捕获失败: {e}")
        return

    # 分析图像
    print(f"\n[{timestamp}] 🤖 第2步：分析图像...")
    try:
        result = scheduler.analyze_and_decide(captured_path)
        print("✓ 分析完成")

        # 打印结果
        analysis = result["analysis"]
        print(f"\n分析结果:")
        print(f"  - 在书桌前: {'✓ 是' if analysis.get('at_desk') else '✗ 否'}")
        print(f"  - 正在玩耍: {'✓ 是' if analysis.get('is_playing') else '✗ 否'}")
        print(f"  - 当前活动: {analysis.get('activity', '未知')}")
        print(f"  - 坐姿状态: {analysis.get('posture', '未知')}")
        print(f"  - 台灯状态: {'✓ 开启' if analysis.get('lamp_on') else '✗ 关闭'}")
        print(f"  - 照明情况: {analysis.get('lighting', '未知')}")

    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 清理
    print("\n清理资源...")
    scheduler.shutdown()
    im_module.shutdown()
    vision_module["camera"].shutdown()
    vision_module["analyzer"].shutdown()

    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_full_cycle()
