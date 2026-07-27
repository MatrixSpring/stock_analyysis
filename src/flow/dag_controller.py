# -*- coding: utf-8 -*-
"""
DAG 上游失败熔断控制器
解决 RunFlow 核心问题：日线/筹码采集失败时，下游 ContextPack 不再浪费资源执行分析

策略（可配置）：
  - abort: 关键数据缺失直接终止下游
  - degrade: 仅标记降级，继续执行（当前默认行为）
  - skip_missing: 跳过缺失的维度，其余继续
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class FailurePolicy(str, Enum):
    ABORT = "abort"            # 终止下游
    DEGRADE = "degrade"        # 降级继续
    SKIP_MISSING = "skip"      # 跳过缺失维度


@dataclass
class DagNodeResult:
    node_id: str
    status: str                # ok / failed / missing / skipped
    message: str = ""
    elapsed_ms: float = 0.0

@dataclass
class DagEdgeRule:
    """上游→下游依赖规则"""
    from_node: str
    to_node: str
    policy: FailurePolicy = FailurePolicy.ABORT
    critical: bool = True      # True = 上游失败直接中止下游


@dataclass
class DagExecutionResult:
    success: bool
    terminated_early: bool = False
    termination_reason: str = ""
    node_results: List[DagNodeResult] = field(default_factory=list)
    skipped_nodes: List[str] = field(default_factory=list)

# ============================================================
# 默认 RunFlow DAG 依赖规则
# ============================================================

DEFAULT_RUNFLOW_RULES: List[DagEdgeRule] = [
    # 日线 K 线 → 技术分析：K 线缺失直接终止
    DagEdgeRule("fetch_daily_kline", "technical_analysis",
                FailurePolicy.ABORT, critical=True),
    # 日线 K 线 → ContextPack：K 线缺失终止
    DagEdgeRule("fetch_daily_kline", "build_context_pack",
                FailurePolicy.ABORT, critical=True),
    # 筹码分布 → 筹码分析：筹码缺失降级继续
    DagEdgeRule("fetch_chip_distribution", "chip_analysis",
                FailurePolicy.DEGRADE, critical=False),
    # 基本面 → 估值分析：基本面缺失降级
    DagEdgeRule("fetch_fundamental", "valuation_analysis",
                FailurePolicy.DEGRADE, critical=False),
    # 新闻 → 舆情分析：新闻缺失跳过
    DagEdgeRule("fetch_news", "sentiment_analysis",
                FailurePolicy.SKIP_MISSING, critical=False),
    # 舆情评论 → 情绪聚合：评论缺失跳过
    DagEdgeRule("fetch_sentiment", "sentiment_agg",
                FailurePolicy.SKIP_MISSING, critical=False),
    # ContextPack → LLM 分析：ContextPack 失败直接终止
    DagEdgeRule("build_context_pack", "llm_analysis",
                FailurePolicy.ABORT, critical=True),
    # LLM 分析 → 报告生成
    DagEdgeRule("llm_analysis", "generate_report",
                FailurePolicy.ABORT, critical=True),
    # 报告 → 通知推送（通知失败不终止）
    DagEdgeRule("generate_report", "send_notification",
                FailurePolicy.DEGRADE, critical=False),
]


# ============================================================
# DAG 控制器
# ============================================================

class DagController:
    """DAG 上游失败熔断控制器"""

    def __init__(self, rules: Optional[List[DagEdgeRule]] = None):
        self._rules = rules or DEFAULT_RUNFLOW_RULES
        # 构建邻接表
        self._downstream: Dict[str, List[DagEdgeRule]] = {}
        for r in self._rules:
            self._downstream.setdefault(r.from_node, []).append(r)

    def should_abort_downstream(self, failed_node_id: str) -> List[str]:
        """
        上游节点失败后，返回应被终止的下游节点列表。
        """
        aborted: List[str] = []
        visited: Set[str] = set()
        queue = [failed_node_id]

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for rule in self._downstream.get(current, []):
                if rule.critical and rule.policy == FailurePolicy.ABORT:
                    aborted.append(rule.to_node)
                queue.append(rule.to_node)

        return list(dict.fromkeys(aborted))

    def evaluate(self, node_results: List[DagNodeResult]) -> DagExecutionResult:
        """
        评估 DAG 执行结果，决定是否终止下游。

        Args:
            node_results: 已执行节点的结果列表

        Returns:
            DagExecutionResult（含终止决策和被跳过的节点列表）
        """
        failed_critical = [
            n for n in node_results
            if n.status in ("failed", "missing")
            and self._is_critical_source(n.node_id)
        ]

        skipped_nodes: List[str] = []
        for fc in failed_critical:
            skipped_nodes.extend(self.should_abort_downstream(fc.node_id))

        terminated = len(skipped_nodes) > 0
        reason = ""
        if terminated:
            failed_labels = [fc.node_id for fc in failed_critical]
            reason = f"上游关键节点失败[{', '.join(failed_labels)}]，终止下游节点: {', '.join(skipped_nodes)}"

        return DagExecutionResult(
            success=not terminated,
            terminated_early=terminated,
            termination_reason=reason,
            node_results=node_results,
            skipped_nodes=skipped_nodes,
        )

    def _is_critical_source(self, node_id: str) -> bool:
        for rule in self._rules:
            if rule.from_node == node_id:
                return rule.critical
        return False

    def add_rule(self, rule: DagEdgeRule):
        self._rules.append(rule)
        self._downstream.setdefault(rule.from_node, []).append(rule)

    def get_rules(self) -> List[Dict]:
        return [{"from": r.from_node, "to": r.to_node, "policy": r.policy.value, "critical": r.critical}
                for r in self._rules]

    def get_skipped_summary(self, result: DagExecutionResult) -> str:
        """生成被跳过节点的诊断面板摘要"""
        if not result.terminated_early:
            return ""
        return f"DAG 熔断: {result.termination_reason}"


# 全局实例
dag_controller = DagController()
