"""
测试脚本 - 验证模块初始化
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

print("=" * 60)
print("学习监工系统 - 模块测试")
print("=" * 60)

# 测试 1: 导入核心模块
print("\n[测试 1/5] 导入核心模块...")
try:
    from core.config import config
    from core.base import BaseModule, Logger, StateManager
    from core.scheduler import Scheduler
    print("✅ 核心模块导入成功")
except Exception as e:
    print(f"❌ 核心模块导入失败: {e}")
    sys.exit(1)

# 测试 2: 导入 Vision 模块
print("\n[测试 2/5] 导入 Vision 模块...")
try:
    from modules.vision import create_vision_module
    print("✅ Vision 模块导入成功")
except Exception as e:
    print(f"❌ Vision 模块导入失败: {e}")
    sys.exit(1)

# 测试 3: 导入 IM 模块
print("\n[测试 3/5] 导入 IM 模块...")
try:
    from modules.im import create_im_module
    print("✅ IM 模块导入成功")
except Exception as e:
    print(f"❌ IM 模块导入失败: {e}")
    sys.exit(1)

# 测试 4: 验证配置
print("\n[测试 4/5] 验证配置...")
try:
    print(f"  - Kimi API Key: {'已配置' if config.kimi.api_key else '未配置'}")
    print(f"  - Kimi 模型: {config.kimi.model}")
    print(f"  - 摄像头索引: {config.camera.camera_index}")
    print(f"  - 企业微信: {'已配置' if config.wechat.corpid else '未配置'}")
    print(f"  - 接收人: {config.wechat.touser}")
    print(f"  - 提醒阈值: {config.scheduler.alert_threshold}次")
    print("✅ 配置验证成功")
except Exception as e:
    print(f"❌ 配置验证失败: {e}")
    sys.exit(1)

# 测试 5: 初始化模块
print("\n[测试 5/5] 初始化模块...")
try:
    # 创建 Vision 模块
    vision_module = create_vision_module(config)
    print("  ✅ Vision 模块创建成功")

    # 创建 IM 模块
    im_module = create_im_module(config)
    im_module.initialize()
    print(f"  ✅ IM 模块初始化成功（{len(im_module.notifiers)} 个通知器）")

    # 创建调度器
    scheduler = Scheduler(config, vision_module["analyzer"], im_module)
    scheduler.initialize()
    print("  ✅ 调度器初始化成功")

except Exception as e:
    print(f"❌ 模块初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 清理
print("\n清理资源...")
im_module.shutdown()
scheduler.shutdown()
vision_module["camera"].shutdown()
vision_module["analyzer"].shutdown()

print("\n" + "=" * 60)
print("✅ 所有测试通过！系统已准备就绪。")
print("=" * 60)
print("\n运行主程序: python main.py")
print()
