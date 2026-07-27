# -*- coding: utf-8 -*-
"""
数据质量自动校验规则引擎
对标 EasyQuant 脏数据过滤、VectorBT 数据对齐校验
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class QualityLevel(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class QualityCheckResult:
    rule_name: str
    level: QualityLevel
    message: str
    field: Optional[str] = None
    value: Any = None
    suggestion: Optional[str] = None


@dataclass
class DataQualityReport:
    check_time: str = ""
    total_records: int = 0
    passed: int = 0
    warnings: int = 0
    errors: int = 0
    critical: int = 0
    details: List[QualityCheckResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_time": self.check_time,
            "total": self.total_records,
            "passed": self.passed,
            "warnings": self.warnings,
            "errors": self.errors,
            "critical": self.critical,
            "issue_rate": round((self.warnings + self.errors + self.critical) / max(1, self.total_records), 3),
        }


class QualityRule:
    """质量规则抽象基类"""

    def __init__(self, name: str, level: QualityLevel = QualityLevel.WARNING):
        self.name = name
        self.level = level

    def check(self, record: Dict[str, Any]) -> Optional[QualityCheckResult]:
        raise NotImplementedError

    def _result(self, message: str, field: str = "", value: Any = None,
                suggestion: str = "") -> QualityCheckResult:
        return QualityCheckResult(self.name, self.level, message, field, value, suggestion)


# ============================================================
# 具体规则
# ============================================================

class MissingFieldRule(QualityRule):
    def __init__(self, required_fields: List[str], **kwargs):
        super().__init__("missing_fields", **kwargs)
        self.required_fields = required_fields

    def check(self, record: Dict[str, Any]) -> Optional[QualityCheckResult]:
        missing = [f for f in self.required_fields if f not in record or record[f] is None]
        if missing:
            return self._result(f"缺失字段: {', '.join(missing)}", field=missing[0],
                                suggestion="检查数据源或补全字段")
        return None


class OHLCConsistencyRule(QualityRule):
    """高开低收逻辑关系校验"""

    def __init__(self, **kwargs):
        super().__init__("ohlc_consistency", QualityLevel.ERROR, **kwargs)

    def check(self, record: Dict[str, Any]) -> Optional[QualityCheckResult]:
        try:
            o, h, l, c = (float(record.get(k, 0)) for k in ("open", "high", "low", "close"))
            if any(v <= 0 for v in (o, h, l, c)):
                return self._result("OHLC 含零值或负值", suggestion="检查数据完整性")
            if not (l <= o <= h) or not (l <= c <= h):
                return self._result(f"价格不一致: O={o} H={h} L={l} C={c}", field="open",
                                    suggestion="检查 OHLC 关系")
        except (ValueError, TypeError) as e:
            return self._result(f"OHLC 解析异常: {e}", suggestion="检查数据类型")
        return None


class PriceJumpRule(QualityRule):
    """价格跳空检测"""

    def __init__(self, threshold: float = 0.15, **kwargs):
        super().__init__("price_jump", **kwargs)
        self.threshold = threshold
        self._prev_close: Optional[float] = None

    def check(self, record: Dict[str, Any]) -> Optional[QualityCheckResult]:
        try:
            curr_open = float(record.get("open", 0))
            if self._prev_close and self._prev_close > 0:
                jump = abs(curr_open - self._prev_close) / self._prev_close
                if jump > self.threshold:
                    result = self._result(
                        f"价格跳空 {jump:.1%} > {self.threshold:.0%}",
                        field="open", value=curr_open,
                        suggestion="检查除权除息/停牌复牌",
                    )
                    self._prev_close = float(record.get("close", curr_open))
                    return result
            self._prev_close = float(record.get("close", curr_open))
        except Exception:
            pass
        return None


class OutlierRule(QualityRule):
    """统计离群值检测"""

    def __init__(self, field: str, lower: float, upper: float, **kwargs):
        super().__init__(f"outlier_{field}", **kwargs)
        self.field = field
        self.lower = lower
        self.upper = upper

    def check(self, record: Dict[str, Any]) -> Optional[QualityCheckResult]:
        value = record.get(self.field)
        if value is None:
            return None
        try:
            v = float(value)
            if v < self.lower or v > self.upper:
                return self._result(f"{self.field}={v} 超出 [{self.lower}, {self.upper}]",
                                    field=self.field, value=v, suggestion="检查异常值")
        except (ValueError, TypeError):
            return self._result(f"{self.field} 值 '{value}' 非数值", field=self.field,
                                suggestion="检查数据类型")
        return None


# ============================================================
# 规则引擎
# ============================================================

class DataQualityChecker:
    """数据质量校验引擎"""

    def __init__(self):
        self._rules: List[QualityRule] = []

    def add_rule(self, rule: QualityRule) -> "DataQualityChecker":
        self._rules.append(rule)
        return self

    def add_rules(self, rules: List[QualityRule]) -> "DataQualityChecker":
        self._rules.extend(rules)
        return self

    def check_batch(self, records: List[Dict[str, Any]],
                    mark_dirty: bool = True) -> DataQualityReport:
        report = DataQualityReport(
            check_time=datetime.utcnow().isoformat(),
            total_records=len(records),
        )
        # 重建有状态的规则
        rules = self._rebuild_stateful()

        for record in records:
            record_issues = []
            for rule in rules:
                try:
                    result = rule.check(record)
                    if result:
                        report.details.append(result)
                        record_issues.append(result)
                        if result.level == QualityLevel.WARNING:
                            report.warnings += 1
                        elif result.level == QualityLevel.ERROR:
                            report.errors += 1
                        elif result.level == QualityLevel.CRITICAL:
                            report.critical += 1
                except Exception as e:
                    logger.debug(f"Rule {rule.name} error: {e}")

            if mark_dirty and record_issues:
                record["_quality"] = max((r.level for r in record_issues),
                                         key=lambda l: {"warning": 1, "error": 2, "critical": 3}.get(l, 0))
                record["_quality_issues"] = [{"rule": r.rule_name, "msg": r.message} for r in record_issues]
            elif mark_dirty:
                record["_quality"] = QualityLevel.PASS.value

        report.passed = report.total_records - (report.warnings + report.errors + report.critical)
        return report

    def _rebuild_stateful(self) -> List[QualityRule]:
        """重建有状态规则的新实例"""
        result = []
        for rule in self._rules:
            if isinstance(rule, PriceJumpRule):
                result.append(PriceJumpRule(threshold=rule.threshold, level=rule.level))
            else:
                result.append(rule)
        return result


# ============================================================
# 预置规则集
# ============================================================

def default_quality_rules() -> List[QualityRule]:
    return [
        MissingFieldRule(["open", "high", "low", "close", "volume"], level=QualityLevel.ERROR),
        OHLCConsistencyRule(),
        PriceJumpRule(threshold=0.15, level=QualityLevel.WARNING),
        OutlierRule("close", 0.01, 10000, level=QualityLevel.ERROR),
    ]


def financial_quality_rules() -> List[QualityRule]:
    return [
        MissingFieldRule(["report_period", "revenue", "net_profit"], level=QualityLevel.ERROR),
        OutlierRule("roe", -100, 100, level=QualityLevel.WARNING),
        OutlierRule("debt_ratio", 0, 200, level=QualityLevel.WARNING),
    ]


def create_quality_checker(preset: str = "equity") -> DataQualityChecker:
    checker = DataQualityChecker()
    rules = default_quality_rules() if preset == "equity" else financial_quality_rules()
    checker.add_rules(rules)
    return checker
