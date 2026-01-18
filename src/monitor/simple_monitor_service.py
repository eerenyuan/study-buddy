"""
简化版 Monitor 服务

使用统一配置文件，支持自动保存/加载
"""
import time
import threading
from datetime import datetime, time as dt_time
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

from src.common import Logger
from .simple_config import MonitorConfig
from .simple_rule_checker import SimpleRuleChecker, create_simple_rule_checker
from .notify_manager import NotifyManager, NotifyResult, NotifyLevel


@dataclass
class MonitorStatus:
    """Monitor 状态"""
    is_monitoring: bool = False
    is_time_scheduler_running: bool = False
    start_time: Optional[datetime] = None
    stop_time: Optional[datetime] = None
    snapshots_processed: int = 0
    notifications_sent: int = 0
    last_notify_result: Optional[NotifyResult] = None
    consecutive_failures: int = 0


class SimpleMonitorService:
    """简化版 Monitor 服务

    职责：
    1. 监控循环管理：start_monitor() / stop_monitor()
    2. 时间调度管理：start_time_scheduler() / stop_time_scheduler()
    3. 业务流程协调：process_snapshot()

    特点：
    - 使用统一配置文件（JSON）
    - 自动保存配置更新
    - 简化的规则检查（key + regexp）
    - 简化的通知逻辑（should_notify_stop）
    """

    def __init__(self,
                 vision_analyzer,
                 messenger_service,
                 camera_service,
                 storage_service,
                 config: MonitorConfig):
        """
        Args:
            vision_analyzer: Vision 分析器
            messenger_service: Messenger 服务
            camera_service: Camera 服务
            storage_service: Storage 服务
            config: Monitor 配置对象
        """
        self.vision = vision_analyzer
        self.messenger = messenger_service
        self.camera = camera_service
        self.storage = storage_service
        self.config = config

        self.logger = Logger(config.log_dir)

        # 规则检查器
        self.rule_checker = create_simple_rule_checker(
            rules=config.rules,
            log_dir=config.log_dir
        )

        # 通知管理器
        self.notify_manager = NotifyManager(
            min_notify_interval=config.min_notify_interval,
            max_notify_interval=config.max_notify_interval,
            consecutive_fail_limit=config.consecutive_fail_limit,
            log_dir=config.log_dir
        )

        # 状态变量
        self._monitoring = False
        self._time_scheduler_running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._time_scheduler_thread: Optional[threading.Thread] = None
        self.status = MonitorStatus()

        self.logger.log("monitor", "info",
                       f"SimpleMonitorService 初始化 - 截图间隔: {config.capture_interval}s")

    # ==================== 配置管理 ====================

    def update_config(self, **kwargs):
        """更新配置并自动保存到文件

        支持所有 MonitorConfig 的字段：
        - rules: 规则列表
        - min_notify_interval: 最小通知间隔（分钟）
        - max_notify_interval: 最大通知间隔（分钟）
        - consecutive_fail_limit: 连续失败次数限制
        - auto_start_time: 每日自动开始时间
        - auto_stop_time: 每日自动停止时间
        - enable_time_scheduler: 是否启用时间调度
        - capture_interval: 截图间隔（秒）
        - preview_duration: 预览时长（秒）
        - enable_preview: 是否启用预览
        """
        # 更新配置对象（会自动保存到文件）
        self.config.update(**kwargs)

        # 同步更新子模块
        if "rules" in kwargs:
            self.rule_checker.update_rules(kwargs["rules"])

        # 如果修改了时间调度配置，需要重新启动时间调度器
        if any(key in kwargs for key in ["enable_time_scheduler", "auto_start_time", "auto_stop_time"]):
            # 先停止旧的调度器
            if self._time_scheduler_running:
                self.stop_time_scheduler()

            # 如果启用了时间调度，启动新的调度器
            if self.config.enable_time_scheduler:
                if self.config.auto_start_time and self.config.auto_stop_time:
                    self.logger.log("monitor", "info",
                                   f"重新启动时间调度器 - 开始: {self.config.auto_start_time}, "
                                   f"停止: {self.config.auto_stop_time}")
                    self.start_time_scheduler()

        if any(key in kwargs for key in ["min_notify_interval", "max_notify_interval", "consecutive_fail_limit"]):
            # 转换为整数类型（前端传来的是字符串）
            self.notify_manager.update_config(
                min_notify_interval=int(kwargs["min_notify_interval"]) if kwargs.get("min_notify_interval") is not None else None,
                max_notify_interval=int(kwargs["max_notify_interval"]) if kwargs.get("max_notify_interval") is not None else None,
                consecutive_fail_limit=int(kwargs["consecutive_fail_limit"]) if kwargs.get("consecutive_fail_limit") is not None else None
            )

        self.logger.log("monitor", "info", f"配置已更新: {list(kwargs.keys())}")

    # ==================== 核心业务流程 ====================

    def process_snapshot(self, image_path: str) -> NotifyResult:
        """处理单张截图（核心业务流程）

        流程：
        1. 调用 Vision 分析图像（获取原始 JSON）
        2. 调用 RuleChecker 检查是否符合规则
        3. 调用 NotifyManager 判断是否通知、是否停止
        4. 保存检测记录到数据库
        5. 如果需要通知，调用 Messenger 发送

        Args:
            image_path: 图片路径

        Returns:
            NotifyResult 对象
        """
        self.logger.log("monitor", "info", f"开始处理截图: {image_path}")

        try:
            # 1. AI 分析
            analysis = self.vision.analyze(image_path)
            self.logger.log("monitor", "info", f"分析结果: {analysis}")

            # 2. 规则检查
            rule_check_result = self.rule_checker.check(analysis)
            self.logger.log("monitor", "info",
                           f"规则检查: {rule_check_result.is_valid}")

            # 3. 通知管理
            notify_result = self.notify_manager.should_notify_stop(rule_check_result.is_valid)
            self.logger.log("monitor", "info",
                           f"通知结果: should_notify={notify_result.should_notify}, "
                           f"should_stop={notify_result.should_stop}, reason={notify_result.reason}")

            # 更新状态
            self.status.last_notify_result = notify_result
            self.status.snapshots_processed += 1
            self.status.consecutive_failures = self.notify_manager.consecutive_failures

            # 4. 保存检测记录
            self._save_detection_record(image_path, notify_result, rule_check_result, analysis)

            # 5. 发送通知
            if notify_result.should_notify:
                self._send_notification(notify_result, image_path, analysis)

            # 6. 检查是否应该停止服务
            if notify_result.should_stop:
                self.logger.log("monitor", "warning", "达到连续失败限制，停止监控")
                self.stop_monitor()

        except Exception as e:
            self.logger.log("monitor", "error", f"处理截图异常: {e}")
            notify_result = NotifyResult(
                should_notify=False,
                should_stop=False,
                level=NotifyLevel.INFO,
                reason=f"处理失败: {str(e)}"
            )

        return notify_result

    def _save_detection_record(self, image_path: str, notify_result: NotifyResult,
                               rule_check_result, analysis: dict):
        """保存检测记录"""
        try:
            issues = list(rule_check_result.failed_fields.values())

            # 保存到数据库
            self.storage.save(
                image_path=image_path,
                is_valid=rule_check_result.is_valid,
                issues=issues,
                should_notify=notify_result.should_notify,
                analysis=analysis
            )

            self.logger.log("monitor", "info", "检测记录已保存")

        except Exception as e:
            self.logger.log("monitor", "error", f"保存检测记录失败: {e}")

    def _send_notification(self, notify_result: NotifyResult, image_path: str, analysis: dict):
        """发送通知

        Args:
            notify_result: 通知结果
            image_path: 图片路径
            analysis: AI分析结果（包含所有key:value）
        """
        try:
            # 构建消息内容
            message = f"Study Buddy Notification\n\n"
            message += f"Consecutive Failures: {self.notify_manager.consecutive_failures}\n\n"

            # 添加所有AI分析结果的key:value
            message += f"Analysis Results:\n"
            for key, value in analysis.items():
                message += f"  {key}: {value}\n"

            message += f"\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            # 发送文本消息
            text_success = self.messenger.send(
                message,
                self._convert_level(notify_result.level)
            )
            self.logger.log("monitor", "info", f"文本消息发送: {'成功' if text_success else '失败'}")

            # 发送图片（无论文本是否成功都尝试发送）
            image_success = self.messenger.send_image(image_path, self._convert_level(notify_result.level))
            self.logger.log("monitor", "info", f"图片消息发送: {'成功' if image_success else '失败'}")

            if text_success or image_success:
                self.status.notifications_sent += 1
            else:
                self.logger.log("monitor", "error", "通知发送失败")

        except Exception as e:
            self.logger.log("monitor", "error", f"发送通知异常: {e}")

    def _convert_level(self, level: NotifyLevel):
        """转换通知级别"""
        from src.messenger import MessageLevel

        if level == NotifyLevel.INFO:
            return MessageLevel.INFO
        elif level == NotifyLevel.WARNING:
            return MessageLevel.WARNING
        elif level == NotifyLevel.DANGER:
            return MessageLevel.DANGER
        else:
            return MessageLevel.INFO

    # ==================== 监控循环管理 ====================

    def start_monitor(self) -> bool:
        """启动监控循环"""
        if self._monitoring:
            self.logger.log("monitor", "warning", "监控循环已在运行")
            return False

        self.logger.log("monitor", "info", "启动监控循环")
        self._monitoring = True
        self.status.is_monitoring = True
        self.status.start_time = datetime.now()

        # 重置通知管理器状态
        self.notify_manager.reset()

        # 在后台线程运行监控循环
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="MonitorLoop",
            daemon=True
        )
        self._monitor_thread.start()

        return True

    def stop_monitor(self) -> bool:
        """停止监控循环

        注意：这个方法可能从监控线程内部调用（通过 process_snapshot），
        也可能从外部调用（通过 API 或时间调度器）。
        """
        if not self._monitoring:
            self.logger.log("monitor", "warning", "监控循环未在运行")
            return False

        self.logger.log("monitor", "info", "停止监控循环")
        self._monitoring = False
        self.status.is_monitoring = False
        self.status.stop_time = datetime.now()

        # 检查是否在监控线程内部调用
        current_thread = threading.current_thread()
        is_called_from_monitor_thread = (
            self._monitor_thread is not None and
            current_thread == self._monitor_thread
        )

        if is_called_from_monitor_thread:
            # 从监控线程内部调用：不能 join 自己，只设置标志
            self.logger.log("monitor", "info", "从监控线程内部调用停止，不等待线程结束")
        else:
            # 从外部调用：等待监控线程结束
            if self._monitor_thread:
                self.logger.log("monitor", "info", "等待监控线程结束...")
                self._monitor_thread.join(timeout=5)
                self._monitor_thread = None

        # 释放摄像头资源
        if self.camera:
            self.camera.shutdown()
            self.logger.log("monitor", "info", "摄像头资源已释放")

        return True

    def _monitor_loop(self):
        """监控循环（后台线程）"""
        # 阶段1：预览（可选）
        if self.config.enable_preview and self.config.preview_duration > 0:
            self._run_preview_phase()

        # 阶段2：监控循环
        self._run_monitor_loop()

    def _run_preview_phase(self):
        """运行预览阶段"""
        duration = self.config.preview_duration
        self.logger.log("monitor", "info", f"启动预览阶段 ({duration}s)")

        # 启动预览
        result = self.camera.start_preview("monitor")
        if not result.get("success"):
            self.logger.log("monitor", "error", f"启动预览失败: {result.get('message')}")
            return

        try:
            # 使用可中断的睡眠
            self._sleep_with_interrupt(duration)
        finally:
            # 停止预览（如果监控已停止，不尝试操作摄像头）
            if self._monitoring:
                self.camera.stop_preview("monitor")
                self.logger.log("monitor", "info", "预览阶段结束，开始监控")
            else:
                self.logger.log("monitor", "info", "预览阶段终止（监控已停止），跳过摄像头操作")

    def _run_monitor_loop(self):
        """运行监控循环"""
        while self._monitoring:
            try:
                # 1. 触发截图
                image_path = self.camera.capture()
                if not image_path:
                    self.logger.log("monitor", "error", "截图失败，跳过本次处理")
                    self._sleep_with_interrupt(self.config.capture_interval)
                    continue

                self.logger.log("monitor", "info", f"监控截图: {image_path}")

                # 2. 处理截图
                self.process_snapshot(image_path)

                # 3. 等待下次截图（可中断）
                self._sleep_with_interrupt(self.config.capture_interval)

            except Exception as e:
                self.logger.log("monitor", "error", f"监控循环异常: {e}")
                self._sleep_with_interrupt(5)

    def _sleep_with_interrupt(self, duration: float):
        """可中断的睡眠（用于快速响应停止信号）"""
        end_time = time.time() + duration
        while self._monitoring and time.time() < end_time:
            # 每次最多睡 0.5 秒，然后检查 _monitoring 标志
            remaining = end_time - time.time()
            if remaining <= 0:
                break
            time.sleep(min(0.5, remaining))

    # ==================== 时间调度管理 ====================

    def start_time_scheduler(self) -> bool:
        """启动时间调度器"""
        if not self.config.enable_time_scheduler:
            self.logger.log("monitor", "info", "时间调度未启用")
            return False

        if self._time_scheduler_running:
            self.logger.log("monitor", "warning", "时间调度器已在运行")
            return False

        if not self.config.auto_start_time or not self.config.auto_stop_time:
            self.logger.log("monitor", "warning", "未配置自动开始/停止时间")
            return False

        self.logger.log("monitor", "info",
                       f"启动时间调度器 - 开始: {self.config.auto_start_time}, "
                       f"停止: {self.config.auto_stop_time}")

        self._time_scheduler_running = True
        self.status.is_time_scheduler_running = True

        # 在后台线程运行时间调度
        self._time_scheduler_thread = threading.Thread(
            target=self._time_scheduler_loop,
            name="TimeScheduler",
            daemon=True
        )
        self._time_scheduler_thread.start()

        return True

    def stop_time_scheduler(self) -> bool:
        """停止时间调度器"""
        if not self._time_scheduler_running:
            self.logger.log("monitor", "warning", "时间调度器未在运行")
            return False

        self.logger.log("monitor", "info", "停止时间调度器")
        self._time_scheduler_running = False
        self.status.is_time_scheduler_running = False

        # 等待时间调度线程结束
        if self._time_scheduler_thread:
            self._time_scheduler_thread.join(timeout=5)
            self._time_scheduler_thread = None

        return True

    def _time_scheduler_loop(self):
        """时间调度循环（后台线程）"""
        # 记录上次检查的日期和分钟
        last_check_date = None
        last_check_minute = None
        last_auto_start_date = None  # 记录上次自动启动的日期

        # 解析配置的时间
        start_hour, start_min = map(int, self.config.auto_start_time.split(':'))
        stop_hour, stop_min = map(int, self.config.auto_stop_time.split(':'))

        while self._time_scheduler_running:
            try:
                now = datetime.now()
                current_date = now.date()
                current_hour = now.hour
                current_min = now.minute
                current_total_min = current_hour * 60 + current_min
                start_total_min = start_hour * 60 + start_min
                stop_total_min = stop_hour * 60 + stop_min

                # 检查是否跨天，如果是新的一天，重置状态
                if last_check_date is None or last_check_date != current_date:
                    self.logger.log("monitor", "info",
                                   f"新的一天: {current_date}, 重置调度状态")
                    last_check_date = current_date
                    last_check_minute= None
                    last_auto_start_date = None  # 新的一天重置自动启动日期

                # 检查当前是否在监控时间段内 [start_time, stop_time)
                in_monitoring_window = (
                    start_total_min <= current_total_min < stop_total_min
                )

                # 检查是否应该启动监控（每天只自动启动一次）
                should_start = (
                    not self._monitoring and  # 未在运行
                    in_monitoring_window and  # 在监控时间段内
                    (last_auto_start_date is None or last_auto_start_date != current_date)  # 今天还没自动启动过（即使因连续失败停机也不会再启动）
                )

                if should_start:
                    self.logger.log("monitor", "info",
                                   f"时间调度器触发启动 - 时间: {now.strftime('%H:%M')}, "
                                   f"监控时段: {self.config.auto_start_time} - {self.config.auto_stop_time}")
                    self.start_monitor()
                    last_auto_start_date = current_date  # 记录自动启动日期
                
                # 检查是否应该停止监控
                should_stop = (
                    self._monitoring and  # 正在运行
                    last_check_minute is not None and last_check_minute<stop_total_min and current_total_min >=stop_total_min  # 刚到达停止时间
                )

                if should_stop:
                    self.logger.log("monitor", "info",
                                   f"时间调度器触发停止 - 时间: {now.strftime('%H:%M')}, "
                                   f"监控时段: {self.config.auto_start_time} - {self.config.auto_stop_time}")
                    self.stop_monitor()
                    
                last_check_minute=current_total_min


                # 每分钟检查一次
                time.sleep(60)

            except Exception as e:
                self.logger.log("monitor", "error", f"时间调度异常: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(60)

    # ==================== 状态查询 ====================

    def get_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        return {
            "is_monitoring": self.status.is_monitoring,
            "is_time_scheduler_running": self.status.is_time_scheduler_running,
            "start_time": self.status.start_time.isoformat() if self.status.start_time else None,
            "stop_time": self.status.stop_time.isoformat() if self.status.stop_time else None,
            "snapshots_processed": self.status.snapshots_processed,
            "notifications_sent": self.status.notifications_sent,
            "consecutive_failures": self.status.consecutive_failures,
            "last_notify_result": {
                "should_notify": self.status.last_notify_result.should_notify if self.status.last_notify_result else None,
                "should_stop": self.status.last_notify_result.should_stop if self.status.last_notify_result else None,
                "reason": self.status.last_notify_result.reason if self.status.last_notify_result else None,
                "level": self.status.last_notify_result.level.value if self.status.last_notify_result else None
            } if self.status.last_notify_result else None,
            "notify_manager": self.notify_manager.get_status(),
            "config": self.config.to_dict()
        }

    def shutdown(self):
        """关闭服务"""
        self.logger.log("monitor", "info", "关闭 SimpleMonitorService")

        # 停止监控循环
        if self._monitoring:
            self.stop_monitor()

        # 停止时间调度
        if self._time_scheduler_running:
            self.stop_time_scheduler()

        self.logger.log("monitor", "info", "SimpleMonitorService 已关闭")


# ==================== 工厂函数 ====================

def create_simple_monitor_service(vision_analyzer,
                                 messenger_service,
                                 camera_service,
                                 storage_service,
                                 config_file: str = "config/monitor_config.json") -> SimpleMonitorService:
    """创建简化版 Monitor 服务

    Args:
        vision_analyzer: Vision 分析器
        messenger_service: Messenger 服务
        camera_service: Camera 服务
        storage_service: Storage 服务
        config_file: 配置文件路径

    Returns:
        SimpleMonitorService 实例
    """
    # 加载配置（如果文件不存在会创建默认配置）
    config = MonitorConfig.load(config_file)

    return SimpleMonitorService(
        vision_analyzer=vision_analyzer,
        messenger_service=messenger_service,
        camera_service=camera_service,
        storage_service=storage_service,
        config=config
    )
