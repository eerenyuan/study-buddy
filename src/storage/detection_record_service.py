"""
检测记录存储服务

职责：
1. 保存检测记录（完整 AI 分析结果）
2. 查询今天的检测记录

存储方式：SQLite 数据库
"""
import sqlite3
import json
import threading
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from pathlib import Path

from src.common import Logger


class DetectionRecordService:
    """检测记录存储服务

    职责：
    1. 保存检测记录（完整 AI 分析结果）
    2. 查询今天的检测记录

    设计原则：
    - 简洁：只实现必要功能
    - 轻量：使用 SQLite，无需额外服务
    - 线程安全：使用锁保护数据库连接
    """

    def __init__(self, db_path: str = "data/detection_records.db", log_dir: str = "logs"):
        """
        Args:
            db_path: 数据库文件路径
            log_dir: 日志目录
        """
        self.db_path = db_path
        self.logger = Logger(log_dir)

        # 线程安全锁
        self._lock = threading.Lock()

        # 确保数据目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self._init_database()

        self.logger.log("storage", "info", f"DetectionRecordService 初始化 - 数据库: {db_path}")

    def _init_database(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS detection_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    image_path TEXT NOT NULL,
                    is_valid BOOLEAN NOT NULL,
                    issues TEXT,
                    should_notify BOOLEAN,
                    analysis_json TEXT NOT NULL
                )
            """)

            # 创建索引（加速查询）
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON detection_records(timestamp)
            """)

            conn.commit()

    def save(self,
             image_path: str,
             is_valid: bool,
             issues: List[str],
             should_notify: bool,
             analysis: dict) -> bool:
        """保存检测记录

        Args:
            image_path: 图片路径
            is_valid: 是否合格
            issues: 问题列表
            should_notify: 是否发送了通知
            analysis: 完整的 AI 分析结果（原始 JSON）

        Returns:
            是否保存成功
        """
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    # 将 issues 和 analysis 序列化为 JSON
                    issues_json = json.dumps(issues, ensure_ascii=False)
                    analysis_json = json.dumps(analysis, ensure_ascii=False)

                    # 使用本地时间而不是 UTC
                    from datetime import datetime
                    local_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    conn.execute("""
                        INSERT INTO detection_records
                        (timestamp, image_path, is_valid, issues, should_notify, analysis_json)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (local_timestamp, image_path, is_valid, issues_json, should_notify, analysis_json))

                    conn.commit()

            self.logger.log("storage", "info",
                           f"保存检测记录: is_valid={is_valid}, issues={len(issues)}")
            return True

        except Exception as e:
            self.logger.log("storage", "error", f"保存检测记录失败: {e}")
            return False

    def get_today(self) -> List[Dict[str, Any]]:
        """获取今天的所有检测记录

        Returns:
            检测记录列表，每条记录包含：
            - id: 记录 ID
            - timestamp: 时间戳
            - image_path: 图片路径
            - is_valid: 是否合格
            - issues: 问题列表
            - should_notify: 是否通知
            - analysis: 完整的 AI 分析结果
        """
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row

                    # 查询今天的记录
                    today = date.today().isoformat()
                    cursor = conn.execute("""
                        SELECT id, timestamp, image_path, is_valid,
                               issues, should_notify, analysis_json
                        FROM detection_records
                        WHERE date(timestamp) = ?
                        ORDER BY timestamp DESC
                    """, (today,))

                    rows = cursor.fetchall()

                    # 转换为字典列表
                    records = []
                    for row in rows:
                        record = {
                            "id": row["id"],
                            "timestamp": row["timestamp"],
                            "image_path": row["image_path"],
                            "is_valid": bool(row["is_valid"]),
                            "issues": json.loads(row["issues"]) if row["issues"] else [],
                            "should_notify": bool(row["should_notify"]),
                            "analysis": json.loads(row["analysis_json"])
                        }
                        records.append(record)

                    self.logger.log("storage", "info", f"查询今天记录: {len(records)} 条")
                    return records

        except Exception as e:
            self.logger.log("storage", "error", f"查询今天记录失败: {e}")
            return []

    def get_status(self) -> Dict[str, Any]:
        """获取存储状态

        Returns:
            状态字典
        """
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    # 总记录数
                    cursor = conn.execute("SELECT COUNT(*) as total FROM detection_records")
                    total = cursor.fetchone()["total"]

                    # 今天的记录数
                    today = date.today().isoformat()
                    cursor = conn.execute("""
                        SELECT COUNT(*) as today_count
                        FROM detection_records
                        WHERE date(timestamp) = ?
                    """, (today,))
                    today_count = cursor.fetchone()["today_count"]

                    return {
                        "db_path": self.db_path,
                        "total_records": total,
                        "today_records": today_count
                    }

        except Exception as e:
            self.logger.log("storage", "error", f"获取存储状态失败: {e}")
            return {
                "db_path": self.db_path,
                "total_records": 0,
                "today_records": 0,
                "error": str(e)
            }


# ==================== 工厂函数 ====================

_service_instance: Optional[DetectionRecordService] = None
_service_lock = threading.Lock()


def get_detection_record_service(db_path: str = "data/detection_records.db",
                                 log_dir: str = "logs") -> DetectionRecordService:
    """获取检测记录存储服务单例

    Args:
        db_path: 数据库文件路径
        log_dir: 日志目录

    Returns:
        DetectionRecordService 单例
    """
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = DetectionRecordService(db_path, log_dir)
    return _service_instance
