"""
Study Buddy - 项目初始化脚本

创建必要的目录结构和配置文件
"""
import os
from pathlib import Path


def create_directory_structure():
    """创建必要的目录结构"""
    print("[INFO] Creating directory structure...")

    directories = [
        "data",
        "data/captures",
        "logs",
        "config"
    ]

    for directory in directories:
        dir_path = Path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"  [OK] {directory}/")


def check_env_file():
    """检查 .env 文件是否存在"""
    print("\n[CHECK] Environment configuration...")

    env_path = Path(".env")
    env_example = Path(".env.example")

    if not env_path.exists():
        if env_example.exists():
            print("  [WARN] .env file not found")
            print(f"  [HELP] Please copy .env.example to .env and configure:")
            print(f"         cp .env.example .env")
            print(f"         Then edit .env to add API keys and settings")
            return False
        else:
            print("  [WARN] .env.example file not found")
            return False
    else:
        print("  [OK] .env file exists")
        return True


def check_config_file():
    """检查配置文件是否存在"""
    print("\n[CHECK] Configuration files...")

    config_path = Path("config/monitor_config.json")

    if not config_path.exists():
        print("  [WARN] config/monitor_config.json not found")
        print("  [INFO] Application will create default config on first run")
        return False
    else:
        print("  [OK] config/monitor_config.json exists")
        return True


def check_data_consistency():
    """检查数据一致性"""
    print("\n[CHECK] Data consistency...")

    db_path = Path("data/detection_records.db")
    captures_dir = Path("data/captures")

    if db_path.exists():
        print("  [INFO] Database file found")

        # 检查是否有图片
        if captures_dir.exists():
            images = list(captures_dir.glob("*.jpg")) + list(captures_dir.glob("*.png"))
            if len(images) == 0:
                print("  [WARN] Database exists but no image files found")
                print("  [WARN] This may cause 'Image not available' error in records page")
                print("  [HELP] If copied from another computer, you need to copy data/captures/ folder too")
                print("  [HELP] Or delete the database to start fresh:")
                print("         rm data/detection_records.db")
                return False
            else:
                print(f"  [OK] Database and {len(images)} images found")
                return True
        else:
            print("  [WARN] Database exists but data/captures/ directory not found")
            print("  [WARN] This will cause 'Image not available' error")
            return False
    else:
        print("  [INFO] Database file not found (first run)")
        return True


def main():
    """主函数"""
    print("=" * 60)
    print("Study Buddy - Project Setup")
    print("=" * 60)

    # 创建目录结构
    create_directory_structure()

    # 检查配置文件
    env_ok = check_env_file()
    config_ok = check_config_file()
    data_ok = check_data_consistency()

    # 总结
    print("\n" + "=" * 60)
    print("Setup Check Complete")
    print("=" * 60)

    if not env_ok:
        print("\n[ERROR] Please create .env file first:")
        print("   cp .env.example .env")
        print("   Then edit .env to add your configuration")
    elif not data_ok:
        print("\n[WARN] Data inconsistency detected. Recommended action:")
        print("   rm data/detection_records.db")
        print("   Then restart the application")
    else:
        print("\n[OK] Everything is ready! You can start the application:")
        print("   cd web")
        print("   python app.py")


if __name__ == "__main__":
    main()
