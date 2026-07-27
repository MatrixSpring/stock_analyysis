# -*- coding: utf-8 -*-
"""
===================================
AI 推理溯源系统 — AnalysisTrace
===================================

职责：
1. 每条 AI 研判结论记录引用来源（指标/数据/新闻/政策）
2. 可复现：相同输入 + 相同模型 → 可回溯验证
3. 可审计：历史分析结论的完整溯源链

输出示例：
{
  conclusion: "建议买入",
  confidence: 0.72,
  evidence: [
    {type: "indicator", name: "MA5上穿MA20", value: "金叉", source: "kline"},
    {type: "capital", name: "北向连续流入", value: "5日净流入30亿", source: "north_bound"},
    {type: "news", name: "政策利好", value: "...", source: "rag_knowledge"},
  ],
  timestamp: "2024-01-15T10:30:00",
  model: "deepseek-chat",
  prompt_version: "v2.1",
}
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Evidence:
    """单条证据"""
    type: str           # indicator / capital / news / policy / macro / technical
    name: str           # 指标/数据名
    value: Any          # 实际值
    source: str = ""     # 数据来源
    confidence: float = 1.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TraceRecord:
    """单次分析的完整溯源记录"""
    trace_id: str
    stock_code: str
    analysis_type: str
    conclusions: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)
    model: str = ""
    prompt_hash: str = ""
    prompt_version: str = ""
    data_snapshot_ref: str = ""   # 快照引用
    vector_context: str = ""       # RAG 检索到的上下文（摘要）
    total_tokens: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    raw_response: str = ""        # LLM 原始响应（可选）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "stock_code": self.stock_code,
            "analysis_type": self.analysis_type,
            "conclusions": self.conclusions,
            "evidence": [
                {"type": e.type, "name": e.name, "value": str(e.value)[:200],
                 "source": e.source, "confidence": e.confidence}
                for e in self.evidence
            ],
            "model": self.model,
            "prompt_hash": self.prompt_hash,
            "prompt_version": self.prompt_version,
            "data_snapshot_ref": self.data_snapshot_ref,
            "total_tokens": self.total_tokens,
            "created_at": self.created_at,
            "evidence_count": len(self.evidence),
        }


class AnalysisTracer:
    """
    AI 推理溯源器。

    使用方式：
        tracer = AnalysisTracer()

        with tracer.trace("600519", "full_analysis") as trace:
            trace.add_evidence("indicator", "MA多头排列", "MA5>MA10>MA20")
            trace.add_evidence("capital", "北向流入", "5日净流入30亿")
            trace.add_conclusion("买入", confidence=0.72, reason="技术面+资金面共振")

        # 保存
        tracer.save(trace)
    """

    def __init__(self, storage_dir: Optional[str] = None):
        self._traces: Dict[str, TraceRecord] = {}
        self._storage_dir = storage_dir

    def create_trace(
        self,
        stock_code: str,
        analysis_type: str = "full_analysis",
        model: str = "",
        prompt_version: str = "",
        data_snapshot_ref: str = "",
    ) -> TraceRecord:
        """创建新的溯源记录"""
        trace_id = hashlib.md5(
            f"{stock_code}:{analysis_type}:{time.time()}".encode()
        ).hexdigest()[:12]

        trace = TraceRecord(
            trace_id=trace_id,
            stock_code=stock_code.upper(),
            analysis_type=analysis_type,
            model=model,
            prompt_version=prompt_version,
            data_snapshot_ref=data_snapshot_ref,
        )

        self._traces[trace_id] = trace
        return trace

    def add_evidence(
        self, trace: TraceRecord, etype: str, name: str,
        value: Any, source: str = "", confidence: float = 1.0,
    ):
        """添加证据"""
        trace.evidence.append(Evidence(
            type=etype, name=name, value=value,
            source=source, confidence=confidence,
        ))

    def add_conclusion(
        self, trace: TraceRecord, conclusion: str,
        confidence: float = 0.5, reason: str = "",
        action: str = "",
    ):
        """添加结论"""
        trace.conclusions.append({
            "conclusion": conclusion,
            "confidence": round(confidence, 2),
            "reason": reason,
            "action": action,
        })

    def set_vector_context(self, trace: TraceRecord, context: str):
        """记录 RAG 检索上下文"""
        trace.vector_context = context

    def finalize(
        self, trace: TraceRecord,
        prompt: str = "",
        raw_response: str = "",
        total_tokens: int = 0,
    ):
        """完成溯源记录"""
        trace.prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:12] if prompt else ""

    def get(self, trace_id: str) -> Optional[TraceRecord]:
        return self._traces.get(trace_id)

    def search(
        self,
        stock_code: Optional[str] = None,
        analysis_type: Optional[str] = None,
    ) -> List[TraceRecord]:
        """按条件查询溯源记录"""
        results = []
        for t in self._traces.values():
            if stock_code and t.stock_code != stock_code.upper():
                continue
            if analysis_type and t.analysis_type != analysis_type:
                continue
            results.append(t)
        return results

    def export_trace_text(self, trace: TraceRecord) -> str:
        """导出人类可读的溯源文本"""
        lines = [
            f"## AI 分析溯源: {trace.stock_code}",
            f"分析类型: {trace.analysis_type}",
            f"模型: {trace.model or 'N/A'}",
            f"Prompt 版本: {trace.prompt_version or 'N/A'}",
            f"Token 消耗: {trace.total_tokens}",
            f"时间: {trace.created_at}",
            "",
            "### 结论",
        ]
        for c in trace.conclusions:
            lines.append(
                f"- {c['conclusion']} (置信度: {c['confidence']}) "
                f"— {c.get('reason', '')}"
            )

        lines.extend(["", "### 证据链", ""])
        for e in trace.evidence:
            lines.append(
                f"- [{e.type}] {e.name}: {e.value} "
                f"(来源: {e.source}, 置信度: {e.confidence})"
            )

        if trace.vector_context:
            lines.extend(["", "### RAG 检索上下文", trace.vector_context[:500]])

        return "\n".join(lines)

    def list_all(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._traces.values()]

    def count(self) -> int:
        return len(self._traces)


# 全局实例
_tracer: Optional[AnalysisTracer] = None


def get_tracer() -> AnalysisTracer:
    global _tracer
    if _tracer is None:
        _tracer = AnalysisTracer()
    return _tracer
