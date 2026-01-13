"""
LLM 调度中心
负责整体调度、决策制定、任务分发
"""
from typing import Dict, Any, Optional
from .base import BaseModule, Logger, StateManager
from .config import Config


class Scheduler(BaseModule):
    """调度器 - 使用 LLM 进行整体调度"""

    def __init__(self, config: Config, vision_module, im_module):
        super().__init__(config)
        self.vision = vision_module
        self.im = im_module
        self.state_manager = StateManager()
        self.logger = Logger(config.log_dir)
        self.running = False

    def initialize(self) -> bool:
        """初始化调度器"""
        self.logger.log("scheduler", "info", "调度器初始化")
        return True

    def shutdown(self):
        """关闭调度器"""
        self.running = False
        self.logger.log("scheduler", "info", "调度器已关闭")

    def analyze_and_decide(self, image_path: str) -> Dict[str, Any]:
        """分析图像并做出决策

        Args:
            image_path: 图片路径

        Returns:
            决策结果
        """
        # 1. 视觉分析
        self.logger.log("scheduler", "info", f"分析图片: {image_path}")

        analysis_result = self.vision.analyze(image_path)
        self.state_manager.update_state(analysis_result)

        # 2. 判断是否需要通知
        decision = self._make_decision(analysis_result)

        # 3. 执行通知（包含文本和图片）
        if decision["should_notify"]:
            self._send_notification(decision, image_path)

        return {
            "analysis": analysis_result,
            "decision": decision
        }

    def _make_decision(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """根据分析结果做出决策

        Args:
            analysis: Kimi 分析结果

        Returns:
            决策结果
        """
        decision = {
            "should_notify": True,  # 每次都发送通知
            "notify_reason": "定期状态报告",
            "notify_level": "info",
            "suggestion": analysis.get("suggestion", "")
        }

        # 根据状态决定通知级别
        is_playing = analysis.get("is_playing", False)
        at_desk = analysis.get("at_desk", True)
        posture = analysis.get("posture", "端正")

        if is_playing:
            decision["notify_level"] = "danger"
            decision["notify_reason"] = "⚠️ 检测到正在玩耍"
        elif not at_desk:
            decision["notify_level"] = "warning"
            decision["notify_reason"] = "⚠️ 不在书桌前"
        elif posture in ["歪坐", "趴着", "不佳"]:
            decision["notify_level"] = "warning"
            decision["notify_reason"] = f"⚠️ 坐姿{posture}"
        else:
            decision["notify_level"] = "info"
            decision["notify_reason"] = "✓ 学习状态良好"

        return decision

    def _send_notification(self, decision: Dict[str, Any], image_path: str = None):
        """发送通知

        Args:
            decision: 决策结果
            image_path: 图片路径（可选）
        """
        level = decision.get("notify_level", "info")
        reason = decision.get("notify_reason", "")
        state = self.state_manager.current_state

        # 构建通知消息 - 纯文本格式（个人版微信兼容）
        if level == "danger":
            title = "🚨 学习状态警告"
        elif level == "warning":
            title = "⚠️ 学习提醒"
        else:
            title = "📝 学习状态报告"

        # 使用纯文本，不用特殊符号（个人版微信兼容性更好）
        message = f"""{title}

{reason}

【详细分析】
在书桌前: {'是' if state.get('at_desk') else '否'}
正在玩耍: {'是' if state.get('is_playing') else '否'}
当前活动: {state.get('activity', '未知')}
坐姿状态: {state.get('posture', '未知')}
台灯状态: {'开启' if state.get('lamp_on') else '关闭'}
照明情况: {state.get('lighting', '未知')}

【完整描述】
{state.get('overall_status', '无')}

【建议】
{state.get('suggestion', '无')}
"""

        # 发送文本通知
        try:
            self.im.notify(message, level)
            self.logger.log("scheduler", "info", f"已发送文本通知: {reason}")
        except Exception as e:
            self.logger.log("scheduler", "error", f"发送文本通知失败: {e}")

        # 发送图片（如果有）
        if image_path:
            try:
                self.im.send_image(image_path)
                self.logger.log("scheduler", "info", "已发送图片")
            except Exception as e:
                self.logger.log("scheduler", "error", f"发送图片失败: {e}")

    def get_summary(self) -> Dict[str, Any]:
        """获取当前状态摘要"""
        state = self.state_manager.current_state
        if not state:
            return {"status": "无数据"}

        return {
            "timestamp": self.state_manager.history[-1]["timestamp"] if self.state_manager.history else None,
            "at_desk": state.get("at_desk"),
            "is_playing": state.get("is_playing"),
            "activity": state.get("activity"),
            "posture": state.get("posture"),
            "lamp_on": state.get("lamp_on"),
            "overall_status": state.get("overall_status")
        }
