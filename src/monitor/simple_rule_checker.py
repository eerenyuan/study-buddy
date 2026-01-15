"""
简化版规则检查器

只支持 key + regexp 的简单匹配
"""
import re
from typing import Dict, Any, List
from dataclasses import dataclass

from src.common import Logger


@dataclass
class RuleCheckResult:
    """规则检查结果"""
    is_valid: bool                    # 是否整体合规
    failed_fields: Dict[str, str]     # 不合规的字段: {字段名: 失败原因}
    passed_fields: List[str]          # 合规的字段列表
    raw_analysis: dict                # 原始 AI 分析结果


class SimpleRuleChecker:
    """简化版规则检查器

    规则格式：{"key": "字段名", "regexp": "正则表达式"}
    - 只支持正则表达式匹配
    - 所有字段都是必需的
    """

    def __init__(self, rules: List[Dict[str, str]], log_dir: str = "logs"):
        """
        Args:
            rules: 规则列表，格式：[{"key": "at_desk", "regexp": "^true$"}, ...]
            log_dir: 日志目录
        """
        self.rules = rules
        self.logger = Logger(log_dir)

        # 验证规则
        self._validate_rules()

        self.logger.log("rule_checker", "info",
                       f"SimpleRuleChecker 初始化 - {len(rules)} 条规则")

    def _validate_rules(self):
        """验证规则配置"""
        for rule in self.rules:
            if "key" not in rule or "regexp" not in rule:
                raise ValueError(f"规则格式错误，必须包含 key 和 regexp: {rule}")

            # 验证正则表达式是否有效
            try:
                re.compile(rule["regexp"])
            except re.error as e:
                raise ValueError(f"无效的正则表达式 [{rule['key']}]: {rule['regexp']}, 错误: {e}")

    def check(self, analysis: Dict[str, Any]) -> RuleCheckResult:
        """检查分析结果是否符合规则

        Args:
            analysis: AI 分析结果（JSON dict）

        Returns:
            RuleCheckResult 对象
        """
        failed_fields = {}
        passed_fields = []

        for rule in self.rules:
            key = rule["key"]
            regexp = rule["regexp"]

            # 检查字段是否存在
            if key not in analysis:
                failed_fields[key] = self._get_friendly_message(key, None, "字段缺失")
                continue

            # 获取字段值
            value = str(analysis[key])

            # 正则匹配
            try:
                if re.match(regexp, value, re.IGNORECASE):
                    passed_fields.append(key)
                else:
                    failed_fields[key] = self._get_friendly_message(key, value, regexp)
            except re.error:
                failed_fields[key] = f"规则配置错误: {regexp}"

        is_valid = len(failed_fields) == 0

        result = RuleCheckResult(
            is_valid=is_valid,
            failed_fields=failed_fields,
            passed_fields=passed_fields,
            raw_analysis=analysis
        )

        self.logger.log("rule_checker", "info",
                       f"规则检查完成 - 合规: {is_valid}, "
                       f"通过: {len(passed_fields)}, 失败: {len(failed_fields)}")

        return result

    def _get_friendly_message(self, key: str, value: str, expected) -> str:
        """生成友好的错误消息

        Args:
            key: 字段名
            value: 实际值
            expected: 期望值（正则表达式或特殊标记）

        Returns:
            友好的错误消息
        """
        # 直接显示 key:value，清晰准确，无需复杂映射
        return f"{key}: {value}"

    def update_rules(self, new_rules: List[Dict[str, str]]):
        """更新规则

        Args:
            new_rules: 新的规则列表，格式：[{"key": "at_desk", "regexp": "^true$"}, ...]
        """
        self.rules = new_rules
        self._validate_rules()

        self.logger.log("rule_checker", "info",
                       f"规则已更新 - {len(new_rules)} 条规则")

    def get_rules(self) -> List[Dict[str, str]]:
        """获取规则列表"""
        return self.rules


def create_simple_rule_checker(rules: List[Dict[str, str]], log_dir: str = "logs") -> SimpleRuleChecker:
    """创建简化版规则检查器

    Args:
        rules: 规则列表，格式：[{"key": "at_desk", "regexp": "^true$"}, ...]
        log_dir: 日志目录

    Returns:
        SimpleRuleChecker 实例
    """
    return SimpleRuleChecker(rules, log_dir)
