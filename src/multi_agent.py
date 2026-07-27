# -*- coding: utf-8 -*-
"""
===================================
多智能体分工研判系统 — MultiAgentOrchestrator
===================================

6 大独立 Agent 并行研判、交叉验证:

  Agent 1 技术Agent → K线、量价、指标形态
  Agent 2 资金Agent → 全维度资金行为
  Agent 3 机构Agent → 研报、预期差、市场观点
  Agent 4 产业Agent → 产业链景气、舆情、供需
  Agent 5 宏观Agent → 地缘、政策、博弈风险
  Agent 6 风控Agent → 信号校验、风险排查、分歧标注

最终由汇总Agent整合输出。
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentReport:
    """单个 Agent 报告"""
    agent_name: str
    conclusion: str         # 看多/看空/中性
    confidence: float = 0.5
    score: float = 50.0
    key_signals: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    reasoning: str = ""
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass
class ConsensusReport:
    """汇总共识报告"""
    stock_code: str
    agents: Dict[str, AgentReport] = field(default_factory=dict)
    consensus: str = "neutral"    # bullish / bearish / neutral / divergent
    consensus_score: float = 50.0
    agreement_ratio: float = 0.0
    key_contradictions: List[str] = field(default_factory=list)
    final_recommendation: str = ""
    risk_level: str = "medium"    # low / medium / high / extreme
    total_duration_ms: float = 0.0


class MultiAgentOrchestrator:
    """
    多智能体编排器。

    使用方式:
        orch = MultiAgentOrchestrator()
        orch.register("technical", tech_agent_fn)
        orch.register("capital", capital_agent_fn)
        ...
        report = orch.analyze("600519", context={...})
    """

    def __init__(self, parallel: bool = True, max_workers: int = 6):
        self._agents: Dict[str, Callable] = {}
        self._parallel = parallel
        self._max_workers = max_workers

    def register(self, name: str, agent_fn: Callable[..., AgentReport]):
        """注册 Agent"""
        self._agents[name] = agent_fn
        logger.info(f"[MultiAgent] 注册: {name}")

    def analyze(
        self, stock_code: str, context: Optional[Dict[str, Any]] = None,
    ) -> ConsensusReport:
        """
        并行执行所有 Agent 并生成共识报告。

        Args:
            stock_code: 股票代码
            context: 各Agent共用的上下文数据

        Returns:
            ConsensusReport
        """
        ctx = context or {}
        agents = {
            "technical": "技术面",
            "capital": "资金行为",
            "institutional": "机构观点",
            "industry": "产业链舆情",
            "macro": "宏观博弈",
            "risk_control": "风控校验",
        }

        results: Dict[str, AgentReport] = {}
        start_time = time.time()

        if self._parallel and len(self._agents) > 1:
            with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                futures = {
                    pool.submit(fn, stock_code, ctx): name
                    for name, fn in self._agents.items()
                }
                for future in as_completed(futures):
                    name = futures[future]
                    try:
                        results[name] = future.result(timeout=60)
                    except Exception as e:
                        logger.error(f"[MultiAgent] {name} 失败: {e}")
                        results[name] = AgentReport(
                            agent_name=name,
                            conclusion="neutral",
                            reasoning=f"执行失败: {e}",
                        )
        else:
            for name, fn in self._agents.items():
                try:
                    results[name] = fn(stock_code, ctx)
                except Exception as e:
                    results[name] = AgentReport(
                        agent_name=name,
                        conclusion="neutral",
                        reasoning=f"执行失败: {e}",
                    )

        total_ms = (time.time() - start_time) * 1000
        return self._build_consensus(stock_code, results, total_ms)

    # ============================================================
    # 共识计算
    # ============================================================

    def _build_consensus(
        self, stock_code: str, results: Dict[str, AgentReport], total_ms: float,
    ) -> ConsensusReport:
        bullish = sum(1 for r in results.values() if r.conclusion == "bullish")
        bearish = sum(1 for r in results.values() if r.conclusion == "bearish")
        neutral = sum(1 for r in results.values() if r.conclusion == "neutral")
        total = len(results)

        # 共识分数
        scores = [r.score for r in results.values()]
        consensus_score = sum(scores) / len(scores) if scores else 50.0

        # 一致性
        max_dir = max(bullish, bearish, neutral)
        agreement_ratio = max_dir / max(total, 1)

        # 共识判定
        if agreement_ratio >= 0.8:
            if bullish > bearish:
                consensus = "bullish"
            elif bearish > bullish:
                consensus = "bearish"
            else:
                consensus = "neutral"
        elif agreement_ratio >= 0.5:
            consensus = "neutral"
        else:
            consensus = "divergent"

        # 矛盾点
        contradictions = []
        high_agents = [n for n, r in results.items() if r.score >= 65]
        low_agents = [n for n, r in results.items() if r.score <= 35]
        if high_agents and low_agents:
            contradictions.append(
                f"多维分歧: {', '.join(high_agents)}看多 vs {', '.join(low_agents)}看空"
            )

        # 汇总风险
        all_risks = []
        for r in results.values():
            all_risks.extend(r.risk_flags)
        risk_level = "extreme" if len(all_risks) >= 5 else \
                     "high" if len(all_risks) >= 3 else \
                     "medium" if len(all_risks) >= 1 else "low"

        # 最终建议
        if consensus == "bullish":
            recommendation = "建议关注，等待技术面确认后介入"
        elif consensus == "bearish":
            recommendation = "建议回避或减仓"
        elif consensus == "divergent":
            recommendation = "信号分歧显著，建议观望等待共识形成"
        else:
            recommendation = "中性判断，维持现有仓位"

        return ConsensusReport(
            stock_code=stock_code,
            agents=results,
            consensus=consensus,
            consensus_score=round(consensus_score, 1),
            agreement_ratio=round(agreement_ratio, 2),
            key_contradictions=contradictions,
            final_recommendation=recommendation,
            risk_level=risk_level,
            total_duration_ms=round(total_ms, 1),
        )

    def to_markdown(self, report: ConsensusReport) -> str:
        """生成 Markdown 汇总报告"""
        lines = [
            f"## 多智能体研判报告: {report.stock_code}",
            f"**共识**: {report.consensus} | **评分**: {report.consensus_score}/100",
            f"**一致性**: {report.agreement_ratio:.0%} | **风险等级**: {report.risk_level}",
            f"**建议**: {report.final_recommendation}",
            "",
            "### 各Agent研判",
        ]
        for name, r in report.agents.items():
            lines.append(
                f"- **{name}** [{r.conclusion}] 评分:{r.score:.0f} 置信度:{r.confidence:.0%}"
            )
            if r.key_signals:
                lines.append(f"  信号: {'; '.join(r.key_signals[:2])}")
        if report.key_contradictions:
            lines.extend(["", "### 关键矛盾", ""])
            for c in report.key_contradictions:
                lines.append(f"- ⚠️ {c}")
        return "\n".join(lines)


# ============================================================
# 双模型路由
# ============================================================

@dataclass
class ModelRoute:
    """模型路由决策"""
    tier: str           # "light" | "heavy"
    model_name: str
    max_tokens: int
    temperature: float
    reason: str


class DualModelRouter:
    """
    双模型分层路由。

    轻量模型 → 快速简析、实时研判 (低延迟/低成本)
    高阶模型 → 深度复盘、多维报告、策略复盘 (高精度)
    """

    LIGHT_MODELS = ["deepseek-chat", "gpt-3.5-turbo", "qwen-turbo"]
    HEAVY_MODELS = ["deepseek-reasoner", "claude-sonnet-4-20250514", "gpt-4o"]

    def __init__(
        self, light_model: str = "deepseek-chat",
        heavy_model: str = "deepseek-reasoner",
    ):
        self._light = light_model
        self._heavy = heavy_model

    def route(self, analysis_type: str, context_size: int = 0) -> ModelRoute:
        """
        根据分析类型自动路由。

        快速分析 → light model
        深度分析 → heavy model
        上下文 > 3000 tokens → heavy model
        """
        quick_types = {"quick_scan", "realtime_check", "signal_check", "brief"}
        deep_types = {"full_analysis", "deep_report", "strategy_review",
                      "multi_dimension", "weekly_review"}

        if analysis_type in quick_types and context_size < 3000:
            return ModelRoute(
                tier="light", model_name=self._light,
                max_tokens=1024, temperature=0.3,
                reason="快速研判场景",
            )
        return ModelRoute(
            tier="heavy", model_name=self._heavy,
            max_tokens=4096, temperature=0.1,
            reason="深度分析场景" if analysis_type in deep_types else f"上下文较大({context_size} tokens)",
        )

    def estimate_cost(self, route: ModelRoute, prompt_tokens: int) -> float:
        """估算成本 (USD)"""
        rates = {
            "deepseek-chat": 0.00027,
            "gpt-3.5-turbo": 0.0015,
            "deepseek-reasoner": 0.00055,
            "claude-sonnet-4-20250514": 0.003,
            "gpt-4o": 0.005,
        }
        rate = rates.get(route.model_name, 0.001)
        return round(prompt_tokens / 1000 * rate, 6)
