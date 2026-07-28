# -*- coding: utf-8 -*-
"""
===================================
多模型共识推演 — 请求/响应 Schema
===================================

向下兼容现有 getMultiModelConsensus 接口，
扩展返回字段（process_logs / diverge_level / model_detail.status），
不破坏原有逻辑。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================
# 请求
# ============================================================

class WeightConfigItem(BaseModel):
    name: str = Field(..., description="模型名称")
    weight: float = Field(..., description="权重百分比 0-100", ge=0, le=100)
    win_rate: Optional[float] = Field(None, description="历史胜率")


class MultiConsensusRequest(BaseModel):
    weight_config: List[WeightConfigItem] = Field(
        default_factory=list,
        description="模型权重配置列表，为空时使用系统默认权重",
    )
    stock_code: Optional[str] = Field(None, description="股票代码，可选")


# ============================================================
# 响应
# ============================================================

class ModelDetailItem(BaseModel):
    name: str
    score: float
    confidence: float
    dynamic_weight: float
    status: str = Field("normal", description="normal / diverge / error")
    desc: str = Field("", description="过程备注")


class ProcessLogItem(BaseModel):
    time: str = Field(..., description="日志时间 HH:MM:SS")
    msg: str = Field(..., description="日志内容")
    type: str = Field("info", description="info / success / warn / error")


class ConsensusResult(BaseModel):
    consensus_score: float = Field(0.5, description="共识综合得分 0-1")
    trend: str = Field("oscillation", description="up / down / oscillation")
    confidence: float = Field(0.0, description="整体置信度 0-1")
    valid_model_count: int = Field(0, description="有效模型数量")
    total_model_count: int = Field(0, description="总模型数量")
    diverge_level: int = Field(0, description="分歧等级 0=无 1=轻微 2=显著")


class ChartModelDataItem(BaseModel):
    """单模型推演轨迹数据点"""
    name: str = ""
    score: float = 0.0
    confidence: float = 0.0
    weight: float = 0.0


class ChartConsensusDataItem(BaseModel):
    """共识拟合数据点"""
    label: str = ""
    consensus_score: float = 0.5


class MultiConsensusData(BaseModel):
    consensus: ConsensusResult = Field(default_factory=ConsensusResult)
    model_detail: List[ModelDetailItem] = Field(default_factory=list)
    chart_model_data: List[ChartModelDataItem] = Field(default_factory=list)
    chart_consensus_data: List[ChartConsensusDataItem] = Field(default_factory=list)
    process_logs: List[ProcessLogItem] = Field(default_factory=list)


class MultiConsensusResp(BaseModel):
    code: int = 200
    msg: str = "ok"
    data: Optional[MultiConsensusData] = None
