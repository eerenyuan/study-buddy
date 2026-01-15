"""
Storage 模块 - 存储服务

当前功能：
- DetectionRecordService：检测记录存储

使用示例：
```python
from src.storage import get_detection_record_service

# 创建服务
storage = get_detection_record_service()

# 保存检测记录
storage.save(
    image_path="/path/to/image.jpg",
    is_valid=False,
    issues=["不在桌前", "坐姿不正确"],
    should_notify=True,
    analysis={"is_desk_present": False, "is_posture_correct": False, ...}
)

# 查询今天的记录
today_records = storage.get_today()
for record in today_records:
    print(f"{record['timestamp']}: {record['is_valid']} - {record['issues']}")
```
"""

from .detection_record_service import (
    DetectionRecordService,
    get_detection_record_service
)

__all__ = [
    'DetectionRecordService',
    'get_detection_record_service',
]
