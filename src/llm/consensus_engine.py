# -*- coding: utf-8 -*-
"""
===================================
多模型语义共识引擎 — ConsensusEngine
===================================

职责：
1. 语义级共识分析（替代关键词匹配）
2. 多模型输出幻觉检测
3. 综合可信度评分

使用方式：
    from src.llm.consensus_engine import ConsensusEngine
    engine = ConsensusEngine()
    result = engine.analyze(model_results, arbitrate_fn=my_llm_fn)
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# 共识结果数据结构
# ============================================================

@dataclass
class DimensionConsensus:
    """单个维度的共识分析结果"""
    dimension: str
    majority_view: str = ""
    views: List[str] = field(default_factory=list)
    agreement_rate: float = 0.0
    dissent: List[str] = field(default_factory=list)
    confidence: float = 0.0  # LLM 置信度


@dataclass
class HallucinationCheck:
    """幻觉检测结果"""
    model: str
    hallucination_risk: float = 0.0  # 0-1, 越高越可疑
    flags: List[str] = field(default_factory=list)
    details: str = ""


@dataclass
class ConsensusResult:
    """完整共识分析结果"""
    status: str = "success"  # success / partial / fail
    trend: DimensionConsensus = field(default_factory=lambda: DimensionConsensus("trend"))
    risk: DimensionConsensus = field(default_factory=lambda: DimensionConsensus("risk"))
    strategy: DimensionConsensus = field(default_factory=lambda: DimensionConsensus("strategy"))
    overall_agreement: float = 0.0  # 综合共识度 0-1
    reliability_score: float = 0.0  # 0-100 可信度评分
    divergence_points: List[str] = field(default_factory=list)
    hallucination_checks: List[HallucinationCheck] = field(default_factory=list)
    final_verdict: str = ""
    success_models: List[str] = field(default_factory=list)
    fail_models: List[str] = field(default_factory=list)
    degradation_level: str = "LEVEL_0"


# ============================================================
# 共识引擎
# ============================================================

class ConsensusEngine:
    """多模型语义共识分析引擎。

    支持两种模式：
    1. LLM 模式（推荐）：用一个轻量模型做共识仲裁
    2. 规则模式（fallback）：当 LLM 不可用时用关键词+规则
    """

    # ---- 维度标签（中英文） ----

    _DIMENSION_LABELS = {
        "trend": "趋势方向",
        "risk": "风险评估",
        "strategy": "操作策略",
    }

    _DIMENSION_CATEGORIES = {
        "trend": {
            "bullish": ["看多", "上涨", "牛市", "上升趋势", "多头", "bullish", "uptrend", "买入"],
            "bearish": ["看空", "下跌", "熊市", "下降趋势", "空头", "bearish", "downtrend", "卖出"],
            "sideways": ["震荡", "盘整", "横盘", "整理", "sideways", "consolidation", "观望"],
        },
        "risk": {
            "low": ["低风险", "风险可控", "安全边际", "风险较低", "low risk"],
            "medium": ["中等风险", "风险适中", "中性风险", "medium risk"],
            "high": ["高风险", "风险较高", "需警惕", "注意风险", "high risk"],
        },
        "strategy": {
            "buy": ["买入", "加仓", "建仓", "增持", "buy", "add", "long"],
            "sell": ["卖出", "减仓", "清仓", "减持", "sell", "reduce", "short"],
            "hold": ["持有", "观望", "等待", "不动", "hold", "wait", "neutral"],
        },
    }

    def __init__(
        self,
        consensus_threshold: float = 0.6,
        reliability_weights: Optional[Dict[str, float]] = None,
        enable_hallucination_check: bool = True,
    ):
        self._threshold = consensus_threshold
        self._reliability_weights = reliability_weights or {
            "agreement": 0.40,    # 模型共识度
            "confidence": 0.30,   # 各自置信度
            "coherence": 0.20,    # 逻辑一致性
            "evidence": 0.10,     # 证据质量
        }
        self._enable_hallucination = enable_hallucination_check

    # ============================================================
    # 主入口
    # ============================================================

    def analyze(
        self,
        model_results: List[Dict[str, Any]],
        arbitrate_fn: Optional[Callable] = None,
    ) -> ConsensusResult:
        """分析多模型输出并生成共识结果。

        Args:
            model_results: [{"model": str, "content": str, "success": bool, ...}]
            arbitrate_fn: async fn(prompt: str) -> str | None, 仲裁 LLM

        Returns:
            ConsensusResult
        """
        valid = [r for r in model_results if r.get("success") and r.get("content")]
        failed = [r.get("model", "unknown") for r in model_results if not r.get("success")]

        if not valid:
            return ConsensusResult(
                status="fail",
                success_models=[],
                fail_models=failed,
                final_verdict="所有模型调用失败，无有效分析结果",
                reliability_score=0.0,
            )

        # 模式选择
        if arbitrate_fn is not None:
            result = self._llm_mode(valid, arbitrate_fn)
        else:
            result = self._rule_mode(valid)

        result.success_models = [r.get("model", "unknown") for r in valid]
        result.fail_models = failed

        # 状态判定
        if failed and not valid:
            result.status = "fail"
        elif result.overall_agreement < self._threshold:
            result.status = "partial"
        else:
            result.status = "success"

        # 幻觉检测
        if self._enable_hallucination:
            result.hallucination_checks = self._detect_hallucinations(valid)

        # 综合可信度
        result.reliability_score = self._calculate_reliability(result)

        logging.info(
            f"[ConsensusEngine] 分析完成: "
            f"共识度={result.overall_agreement:.1%}, "
            f"可信度={result.reliability_score:.0f}, "
            f"状态={result.status}"
        )

        return result

    # ============================================================
    # LLM 模式
    # ============================================================

    def _llm_mode(
        self, valid_results: List[Dict[str, Any]],
        arbitrate_fn: Callable,
    ) -> ConsensusResult:
        """用 LLM 做共识仲裁"""
        # 构建仲裁 prompt
        opinions_text = "\n\n---\n\n".join(
            f"【模型: {r['model']}】\n{r['content'][:2000]}"
            for r in valid_results
        )

        prompt = f"""你是一个金融分析共识仲裁器。下列是多个 AI 模型对同一支股票的研判结果。

请分析并输出 JSON（不要 markdown 代码块）：

{opinions_text}

要求：
1. 找出各模型在"趋势方向"、"风险评估"、"操作策略"三个维度的共识和分歧
2. 标注共识度和分歧点
3. 给出综合可信度评分 (0-100)

输出格式：
{{
  "trend": {{"majority": "bullish/sideways/bearish", "agreement": 0.0-1.0, "summary": "..."}},
  "risk": {{"majority": "low/medium/high", "agreement": 0.0-1.0, "summary": "..."}},
  "strategy": {{"majority": "buy/hold/sell", "agreement": 0.0-1.0, "summary": "..."}},
  "overall_agreement": 0.0-1.0,
  "divergence": ["分歧1", "分歧2"],
  "reliability": 0-100,
  "verdict": "一句话最终结论"
}}"""

        try:
            import asyncio

            # 判断 arbitrate_fn 是否是 async
            if asyncio.iscoroutinefunction(arbitrate_fn):
                response = asyncio.get_event_loop().run_until_complete(
                    arbitrate_fn(prompt)
                )
            else:
                response = arbitrate_fn(prompt)
        except RuntimeError:
            response = arbitrate_fn(prompt)

        # 解析 LLM 响应
        try:
            if isinstance(response, str):
                # 尝试提取 JSON
                parsed = self._extract_json(response)
            elif isinstance(response, dict):
                parsed = response
            else:
                parsed = self._extract_json(str(response))
        except Exception:
            logger.warning("[ConsensusEngine] LLM 仲裁解析失败，回退到规则模式")
            return self._rule_mode(valid_results)

        return self._build_from_llm_response(parsed, valid_results)

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """从 LLM 输出中提取 JSON"""
        # 去除 markdown 代码块
        text = re.sub(r'```(?:json)?\s*', '', text)
        text = text.strip()

        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试提取 { } 块
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return json.loads(match.group(0))

        return {}

    def _build_from_llm_response(
        self, parsed: Dict[str, Any], valid_results: List[Dict[str, Any]],
    ) -> ConsensusResult:
        """从 LLM 响应构建 ConsensusResult"""
        trend = parsed.get("trend", {})
        risk = parsed.get("risk", {})
        strategy = parsed.get("strategy", {})

        return ConsensusResult(
            trend=DimensionConsensus(
                dimension="trend",
                majority_view=trend.get("majority", "unknown"),
                agreement_rate=trend.get("agreement", 0.0),
                confidence=0.8,
            ),
            risk=DimensionConsensus(
                dimension="risk",
                majority_view=risk.get("majority", "medium"),
                agreement_rate=risk.get("agreement", 0.0),
                confidence=0.8,
            ),
            strategy=DimensionConsensus(
                dimension="strategy",
                majority_view=strategy.get("majority", "hold"),
                agreement_rate=strategy.get("agreement", 0.0),
                confidence=0.8,
            ),
            overall_agreement=parsed.get("overall_agreement", 0.5),
            divergence_points=parsed.get("divergence", []),
            reliability_score=float(parsed.get("reliability", 50)),
            final_verdict=parsed.get("verdict", ""),
        )

    # ============================================================
    # 规则模式（fallback）
    # ============================================================

    def _rule_mode(
        self, valid_results: List[Dict[str, Any]],
    ) -> ConsensusResult:
        """基于规则的关键词共识分析"""
        model_count = len(valid_results)

        # 对每个维度做规则分析
        trend = self._rule_dimension(valid_results, "trend", model_count)
        risk = self._rule_dimension(valid_results, "risk", model_count)
        strategy = self._rule_dimension(valid_results, "strategy", model_count)

        # 综合共识度
        overall = (trend.agreement_rate + risk.agreement_rate + strategy.agreement_rate) / 3.0

        # 分歧点
        divergence = []
        for dim in [trend, risk, strategy]:
            if dim.agreement_rate < self._threshold:
                detail = "; ".join(dim.dissent[:3]) if dim.dissent else f"{self._DIMENSION_LABELS[dim.dimension]}意见分散"
                divergence.append(f"{self._DIMENSION_LABELS[dim.dimension]}: {detail}")

        # 最终结论
        verdict = self._build_rule_verdict(trend, risk, strategy, overall)

        return ConsensusResult(
            trend=trend,
            risk=risk,
            strategy=strategy,
            overall_agreement=round(overall, 2),
            divergence_points=divergence,
            final_verdict=verdict,
        )

    def _rule_dimension(
        self, results: List[Dict[str, Any]],
        dimension: str, total: int,
    ) -> DimensionConsensus:
        """规则分析单个维度"""
        categories = self._DIMENSION_CATEGORIES.get(dimension, {})
        views = []

        for r in results:
            content = r.get("content", "")
            # 分类
            matched = self._classify_content(content, categories)
            views.append(matched)

        # 统计
        counter = Counter(views)
        if not counter:
            return DimensionConsensus(
                dimension=dimension,
                majority_view="unknown",
                agreement_rate=0.0,
            )

        # 去除非有效分类的计数
        top = counter.most_common(1)[0]
        majority = top[0] if top[0] != "unknown" else "unknown"
        rate = top[1] / max(total, 1)

        others = [k for k in counter if k != majority and k != "unknown"]

        return DimensionConsensus(
            dimension=dimension,
            majority_view=majority,
            views=views,
            agreement_rate=round(rate, 2),
            dissent=others,
        )

    @staticmethod
    def _classify_content(content: str, categories: Dict[str, List[str]]) -> str:
        """判断内容属于哪个类别（加权关键词匹配）"""
        if not content:
            return "unknown"
        text_lower = content.lower()
        scores = {}
        for cat, keywords in categories.items():
            # 加权：越长的关键词权重越高
            scores[cat] = sum(
                len(kw) for kw in keywords if kw.lower() in text_lower
            )
        if not scores or max(scores.values()) == 0:
            return "unknown"
        return max(scores, key=scores.get)

    def is_similar_view(self, text1: str, text2: str) -> bool:
        """核心观点相似度判定（关键词重合度法）。

        两段文本的观点相似度 = 相同关键词 / 总关键词
        阈值 > 0.5 判定为共识。
        """
        key_words = [
            "上涨", "下跌", "震荡", "看多", "看空",
            "风险", "机会", "买入", "卖出", "观望",
            "牛市", "熊市", "突破", "回调", "盘整",
            "强势", "弱势", "放量", "缩量", "背离",
        ]
        view1 = [w for w in key_words if w in text1]
        view2 = [w for w in key_words if w in text2]

        if not view1 and not view2:
            return True  # 都无明确观点 → 保守判为相似

        same = set(view1) & set(view2)
        # 使用用户原始公式：相同关键词 / 最大观点数
        max_views = max(len(view1), len(view2))
        return len(same) / max_views > 0.5 if max_views > 0 else True

    def pairwise_consensus(self, results: List[Dict[str, Any]]) -> float:
        """两两对比模型输出，计算平均共识率。

        Returns:
            0.0-1.0 共识率
        """
        valid = [r for r in results if r.get("content")]
        if len(valid) < 2:
            return 1.0 if len(valid) == 1 else 0.0

        matches = 0
        pairs = 0
        for i in range(len(valid)):
            for j in range(i + 1, len(valid)):
                pairs += 1
                if self.is_similar_view(valid[i]["content"], valid[j]["content"]):
                    matches += 1

        return matches / max(pairs, 1)

    def _build_rule_verdict(
        self, trend: DimensionConsensus, risk: DimensionConsensus,
        strategy: DimensionConsensus, overall: float,
    ) -> str:
        """构建规则模式最终结论"""
        parts = []

        if overall >= 0.8:
            consensus_level = "【高可信】多模型高度共识"
        elif overall >= 0.5:
            consensus_level = "【中可信】存在小幅分歧，建议审慎参考"
        else:
            consensus_level = "【低可信】模型分歧显著，不建议据此操作"

        parts.append(consensus_level)

        trend_cn = {"bullish": "看多", "bearish": "看空", "sideways": "震荡", "unknown": "未知"}
        risk_cn = {"low": "风险较低", "medium": "风险适中", "high": "风险较高", "unknown": "未知"}
        strategy_cn = {"buy": "买入关注", "hold": "持有观望", "sell": "卖出回避", "unknown": "未知"}

        parts.append(
            f"趋势: {trend_cn.get(trend.majority_view, trend.majority_view)} "
            f"(共识度 {trend.agreement_rate:.0%})"
        )
        parts.append(
            f"风险: {risk_cn.get(risk.majority_view, risk.majority_view)}"
        )
        parts.append(
            f"策略: {strategy_cn.get(strategy.majority_view, strategy.majority_view)}"
        )

        return "\n".join(parts)

    # ============================================================
    # 幻觉检测
    # ============================================================

    def _detect_hallucinations(
        self, valid_results: List[Dict[str, Any]],
    ) -> List[HallucinationCheck]:
        """检测各模型输出中的潜在幻觉"""
        checks = []

        for r in valid_results:
            content = r.get("content", "")
            model = r.get("model", "unknown")
            flags = []
            risk_score = 0.0

            # 规则 1: 输出过短（可能无意义）
            if len(content) < 20:
                flags.append("输出过短")
                risk_score += 0.3

            # 规则 2: 自相矛盾（同时说看多和看空）
            bullish_terms = len(re.findall(r'看多|上涨|牛市|买入|bullish', content))
            bearish_terms = len(re.findall(r'看空|下跌|熊市|卖出|bearish', content))
            if bullish_terms >= 2 and bearish_terms >= 2:
                flags.append("方向矛盾（同时含看多和看空信号）")
                risk_score += 0.3

            # 规则 3: 缺乏具体数据
            if not re.search(r'\d+(?:\.\d+)?%', content):
                flags.append("缺乏具体数据支撑")
                risk_score += 0.15

            # 规则 4: 过度使用模糊词汇
            vague_count = len(re.findall(
                r'可能|或许|大概|也许|说不定|不清楚|不确定|难以判断', content
            ))
            if vague_count >= 5:
                flags.append(f"过度模糊 (出现{vague_count}次)")
                risk_score += 0.15

            # 规则 5: 极端绝对化表述
            absolute_count = len(re.findall(
                r'绝对|必然|一定|肯定|毫无疑问|毋庸置疑|百分之百|稳赚|暴涨|暴跌', content
            ))
            if absolute_count >= 3:
                flags.append(f"绝对化表述过多 (出现{absolute_count}次)")
                risk_score += 0.2

            risk_score = min(risk_score, 1.0)

            if flags or risk_score > 0.2:
                checks.append(HallucinationCheck(
                    model=model,
                    hallucination_risk=round(risk_score, 2),
                    flags=flags,
                    details=f"检测到 {len(flags)} 个可疑信号" if flags else "低风险",
                ))

        return checks

    # ============================================================
    # 可信度评分
    # ============================================================

    def _calculate_reliability(self, result: ConsensusResult) -> float:
        """计算综合可信度评分 0-100。

        加权因素：
        - 模型共识度 (40%)
        - 模型数量 (越多越好)
        - 是否存在幻觉标记
        - 分歧程度
        """
        score = 0.0

        # 共识度贡献 (40%)
        score += result.overall_agreement * 40.0

        # 模型数量贡献 (max 30%)
        model_count = len(result.success_models)
        model_score = min(model_count / 5, 1.0) * 30.0  # 5个模型即满分
        score += model_score

        # 幻觉惩罚 (max -20%)
        if result.hallucination_checks:
            avg_risk = sum(h.hallucination_risk for h in result.hallucination_checks) / len(result.hallucination_checks)
            score -= avg_risk * 20.0

        # 分歧惩罚 (max -10%)
        divergence_penalty = min(len(result.divergence_points) * 3, 10)
        score -= divergence_penalty

        # 失败模型惩罚
        if result.fail_models:
            fail_ratio = len(result.fail_models) / max(len(result.success_models) + len(result.fail_models), 1)
            score -= fail_ratio * 10.0

        return round(max(0.0, min(100.0, score)), 1)


# ============================================================
# P3: 多模型动态自适应加权共识（修复静态权重 + 容错兜底）
# ============================================================

def multi_model_consensus_merge(model_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """多模型动态加权共识融合。

    修复：
      - 静态权重固化 → 根据近期胜率动态自适应
      - 单模型异常崩溃 → 自动降级兜底，不中断整体计算

    Args:
        model_results: [{"score":0.65, "confidence":0.8, "recent_win_rate":0.7, ...}, ...]

    Returns:
        {consensus_score, trend, confidence, valid_model_count, total_model_count}
    """
    valid = []
    weight_sum = 0.0

    # 容错过滤异常模型
    for res in model_results:
        if not res or res.get("score") is None:
            continue
        w = float(res.get("recent_win_rate", 0.2) or 0.2)
        w = max(0.05, min(1.0, w))  # clamp [0.05, 1.0]
        valid.append({**res, "dynamic_weight": w})
        weight_sum += w

    # 兜底：无有效模型返回默认平稳预测
    if not valid or weight_sum == 0:
        return {
            "consensus_score": 0.5, "trend": "oscillation",
            "confidence": 0.0, "valid_model_count": 0,
            "total_model_count": len(model_results),
        }

    # 动态加权共识
    final_score = sum(
        float(r["score"]) * r["dynamic_weight"] for r in valid
    ) / weight_sum
    confidence = sum(
        float(r.get("confidence", 0.5)) * r["dynamic_weight"] for r in valid
    ) / weight_sum

    trend = (
        "up" if final_score > 0.55
        else "down" if final_score < 0.45
        else "oscillation"
    )

    return {
        "consensus_score": round(final_score, 4),
        "trend": trend,
        "confidence": round(confidence, 4),
        "valid_model_count": len(valid),
        "total_model_count": len(model_results),
    }


# ============================================================
# 便捷函数
# ============================================================

def build_consensus_summary_markdown(result: ConsensusResult) -> str:
    """将共识结果渲染为 Markdown 摘要"""
    lines = [
        "## 📊 多模型共识分析",
        "",
        f"**综合共识度**: {result.overall_agreement:.0%} | **可信度评分**: {result.reliability_score}/100",
        f"**成功模型**: {', '.join(result.success_models)} | **状态**: {result.status}",
        "",
        "### 各维度共识",
        "",
    ]

    trend_cn = {
        "bullish": "🟢 看多", "bearish": "🔴 看空",
        "sideways": "🟡 震荡", "unknown": "❓ 未定",
    }
    risk_cn = {
        "low": "🟢 较低", "medium": "🟡 适中",
        "high": "🔴 较高", "unknown": "❓ 未知",
    }
    strategy_cn = {
        "buy": "🟢 买入/关注", "hold": "🟡 持有/观望",
        "sell": "🔴 卖出/回避", "unknown": "❓ 未定",
    }

    dims = [
        ("趋势方向", result.trend, trend_cn),
        ("风险评估", result.risk, risk_cn),
        ("操作策略", result.strategy, strategy_cn),
    ]
    for label, dim, cn_map in dims:
        view_cn = cn_map.get(dim.majority_view, dim.majority_view)
        lines.append(
            f"- **{label}**: {view_cn} (共识度 {dim.agreement_rate:.0%})"
        )

    if result.divergence_points:
        lines.append("")
        lines.append("### ⚠️ 分歧点")
        for d in result.divergence_points:
            lines.append(f"- {d}")

    if result.hallucination_checks:
        lines.append("")
        lines.append("### 🔍 幻觉检测")
        for h in result.hallucination_checks:
            if h.hallucination_risk > 0.3:
                icon = "🔴"
            elif h.hallucination_risk > 0.1:
                icon = "🟡"
            else:
                icon = "🟢"
            lines.append(
                f"- {icon} **{h.model}**: 风险={h.hallucination_risk:.0%} "
                f"{'⚠️ ' + ', '.join(h.flags) if h.flags else ''}"
            )

    lines.append("")
    lines.append(f"> {result.final_verdict}" if result.final_verdict else "")

    return "\n".join(lines)


# ============================================================
# 分市场场景化 Prompt 构建器
# ============================================================

def build_market_specific_prompt(
    stock_code: str,
    stock_name: str,
    market_type: str = "A股",
    include_dimensions: Optional[List[str]] = None,
) -> str:
    """构建分市场差异化的分析 Prompt。

    解决通用 Prompt 对不同市场适配差的问题：
    - A股：关注政策催化、板块轮动、北向资金、龙虎榜
    - 港股：关注外围市场、汇率、机构持仓、海外舆情
    - 美股：关注宏观经济、财报预期、社交舆情、期权情绪
    - ETF：关注板块景气度、资金抱团、指数走势、行业政策

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        market_type: 市场类型 (A股/港股/美股/ETF)
        include_dimensions: 额外分析维度

    Returns:
        场景化 prompt 字符串
    """
    dims = include_dimensions or [
        "技术形态", "资金流向", "基本面估值", "行业景气", "舆情催化",
    ]
    dim_text = "、".join(dims)

    base = (
        f"请对{market_type}标的【{stock_name}({stock_code})】进行专业量化股票分析，"
        f"严格遵守以下规则：\n"
        f"1. 输出必须量化、有数据支撑，禁止模糊主观话术\n"
        f"2. 从{', '.join(dims[:5])}等维度分析\n"
        f"3. 明确标注短期走势/中长期走势、涨跌概率、风险等级\n"
        f"4. 区分短期震荡、短期上涨、短期下跌、中长期走强、中长期走弱\n"
        f"5. 风险提示必须量化：回撤空间、波动风险、政策风险、资金出逃风险\n"
        f"6. 给出可落地的操作建议与风险提示\n"
    )

    # ---- 市场差异化 Prompt ----
    market_specific = _get_market_specific_instructions(market_type)

    return base + market_specific


def _get_market_specific_instructions(market_type: str) -> str:
    """获取市场专属分析指令"""
    market_type = market_type.strip()

    if market_type == "A股" or "A" in market_type:
        return (
            "\n【A股专属分析重点】\n"
            "- 政策催化：各部委/产业政策对板块的实质利好/利空\n"
            "- 板块轮动：当前热点板块强弱、龙头对标、轮动节奏\n"
            "- 北向资金：陆股通持仓变化、连续流入/流出趋势\n"
            "- 龙虎榜：机构/游资席位动向、买卖力度对比\n"
            "- 筹码结构：筹码集中度、套牢盘压力、获利盘兑现风险\n"
            "- T+1 制度考量：隔夜风险、涨停板溢价持续性"
        )
    elif "港股" in market_type:
        return (
            "\n【港股专属分析重点】\n"
            "- 外围市场情绪：美股/亚太市场联动影响\n"
            "- 汇率影响：人民币/港币汇率对资金流向的传导\n"
            "- 机构持仓：南向资金、外资投行持仓变化\n"
            "- 海外舆情：国际投行评级调整、做空报告风险\n"
            "- 流动性评估：日均成交额、买卖价差、流动性折价"
        )
    elif "美股" in market_type:
        return (
            "\n【美股专属分析重点】\n"
            "- 宏观经济：美联储政策、就业/通胀数据、GDP 预期\n"
            "- 财报预期：EPS 预期差、营收增速、指引变化\n"
            "- 社交舆情：Reddit/X 情绪、Polymarket 博弈概率\n"
            "- 期权情绪：Put/Call Ratio、未平仓合约集中度\n"
            "- 做空压力：空头持仓比例、Gamma Squeeze 风险"
        )
    elif "ETF" in market_type:
        return (
            "\n【ETF专属分析重点】\n"
            "- 板块景气度：对应行业营收/利润/订单/产能趋势\n"
            "- 资金抱团：机构配置比例变化、ETF 份额变动\n"
            "- 指数走势：跟踪指数技术形态、权重股表现\n"
            "- 行业政策：产业政策支持力度、监管风险\n"
            "- 折溢价：ETF 净值折溢价率、套利机会"
        )
    else:
        return (
            "\n【通用分析重点】\n"
            "- 技术形态：均线系统、MACD/KDJ/RSI 信号\n"
            "- 资金流向：主力资金、成交量异动\n"
            "- 基本面：PE/PB 分位、ROE、营收增速\n"
            "- 风险：波动率、最大回撤、下行风险"
        )


def build_multi_model_analysis_prompt(
    stock_context: str,
    market_type: str = "A股",
    analysis_depth: str = "standard",
) -> str:
    """构建多模型共识分析用的统一 Prompt。

    Args:
        stock_context: 股票行情数据上下文
        market_type: 市场类型
        analysis_depth: 分析深度 (quick/standard/deep)

    Returns:
        供多模型并行调用的 prompt
    """
    depth_instructions = {
        "quick": "请进行快速研判，控制在 200 字以内，仅输出核心结论和关键风险点。",
        "standard": "请进行标准分析，500 字左右，覆盖趋势、风险、策略三个维度。",
        "deep": (
            "请进行深度复盘分析，1000 字以上，覆盖技术面、资金面、基本面、"
            "行业景气度、舆情催化五大维度，给出量化评分和概率预测。"
        ),
    }
    depth_inst = depth_instructions.get(analysis_depth, depth_instructions["standard"])
    market_inst = _get_market_specific_instructions(market_type)

    return (
        f"你是一个专业的{market_type}量化分析师。{depth_inst}\n\n"
        f"{market_inst}\n\n"
        f"=== 股票数据 ===\n{stock_context}\n\n"
        f"请输出分析结果。"
    )
