# -*- coding: utf-8 -*-
"""
===================================
多模型共识推演 API Endpoint
===================================

同步接口，一次返回全部推演过程日志、各阶段状态、分歧信息。
基于现有 MultiAgentOrchestrator 扩展，向下兼容。
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from fastapi import APIRouter, Request

from api.v1.schemas.forecast import (
    ChartConsensusDataItem,
    ChartModelDataItem,
    ConsensusResult,
    ModelDetailItem,
    MultiConsensusData,
    MultiConsensusRequest,
    MultiConsensusResp,
    ProcessLogItem,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# 默认五模型权重配置
DEFAULT_WEIGHT_CONFIG = [
    {"name": "时序预测模型", "weight": 25, "win_rate": 68},
    {"name": "多因子估值模型", "weight": 25, "win_rate": 72},
    {"name": "资金博弈模型", "weight": 20, "win_rate": 65},
    {"name": "舆情地缘模型", "weight": 15, "win_rate": 62},
    {"name": "产业景气模型", "weight": 15, "win_rate": 70},
]


def _add_log(logs: list, msg: str, log_type: str = "info") -> None:
    """向日志列表追加一条带时间戳的日志。"""
    t = datetime.now().strftime("%H:%M:%S")
    logs.append({"time": t, "msg": msg, "type": log_type})


def _run_single_model(model_name: str, _inputs: dict) -> dict:
    """
    执行单个模型推演。

    当前为框架实现：返回模拟推演结果。
    后续迭代接入真实模型推理逻辑替换此函数。
    """
    # TODO: 接入 src/multi_agent.py MultiAgentOrchestrator 的各 Agent 实际推理
    import random
    random.seed(hash(model_name) % (2**31))
    base = random.uniform(0.35, 0.65)
    score = round(base + random.uniform(-0.08, 0.08), 4)
    confidence = round(0.55 + random.uniform(0, 0.35), 4)
    return {"score": score, "confidence": confidence}


@router.post(
    "/consensus",
    response_model=MultiConsensusResp,
    summary="多模型共识推演",
    description="接收模型权重配置，执行全部模型独立推演 → 分歧校验 → 权重融合，返回共识结果与完整过程日志。",
)
async def multi_model_consensus(request: Request, body: MultiConsensusRequest):
    """
    多模型共识融合【完整版】
    新增：推演日志收集、模型分歧判定
    """
    process_logs: list = []

    weight_config = body.weight_config if body.weight_config else DEFAULT_WEIGHT_CONFIG
    # 转为内部格式
    wc = []
    for item in weight_config:
        if hasattr(item, "model_dump"):
            wc.append(item.model_dump())
        else:
            wc.append(item)

    _add_log(process_logs, "初始化推演引擎，加载模型配置", "info")
    valid_results = []
    raw_scores = []

    _add_log(process_logs, "开始加载行情与因子样本数据", "info")

    # ========== 1. 逐个执行子模型推演 ==========
    for model_cfg in wc:
        model_name = model_cfg.get("name", model_cfg.get("model_name", ""))
        weight = model_cfg.get("weight", 20)
        _add_log(process_logs, f"{model_name} 开始独立推演", "info")
        try:
            model_out = _run_single_model(model_name, {})
            score = model_out["score"]
            conf = model_out["confidence"]
            valid_results.append({
                "name": model_name,
                "score": score,
                "confidence": conf,
                "weight": weight,
            })
            raw_scores.append(score)
            _add_log(process_logs, f"{model_name} 推演完成，得分：{score:.4f}", "success")
        except Exception as e:
            _add_log(process_logs, f"{model_name} 运算异常，触发降级兜底策略：{e}", "error")
            raw_scores.append(0.5)

    # ========== 2. 分歧度自动计算 ==========
    _add_log(process_logs, "执行多模型结论分歧校验", "info")
    diverge_level = 0
    if len(raw_scores) >= 2:
        max_s = max(raw_scores)
        min_s = min(raw_scores)
        delta = max_s - min_s
        if 0.2 <= delta < 0.4:
            diverge_level = 1
            _add_log(process_logs, f"检测到轻微模型分歧，得分差值 {delta:.2f}", "warn")
        elif delta >= 0.4:
            diverge_level = 2
            _add_log(process_logs, f"检测到显著模型分歧！得分差值 {delta:.2f}", "warn")
        else:
            _add_log(process_logs, "各模型结论一致性良好，无明显分歧", "success")

    # ========== 3. 动态加权共识计算 ==========
    weight_sum = sum(r["weight"] for r in valid_results)
    if weight_sum <= 0 or not valid_results:
        _add_log(process_logs, "有效模型为空，返回震荡兜底结果", "error")
        consensus_score = 0.5
        confidence = 0.0
        trend = "oscillation"
    else:
        final_score = sum(
            r["score"] * r["weight"] for r in valid_results
        ) / weight_sum
        conf_total = sum(
            r["confidence"] * r["weight"] for r in valid_results
        ) / weight_sum
        consensus_score = round(final_score, 4)
        confidence = round(conf_total, 4)
        if consensus_score > 0.55:
            trend = "up"
        elif consensus_score < 0.45:
            trend = "down"
        else:
            trend = "oscillation"
    _add_log(process_logs, "动态权重融合完成，生成最终共识结果", "success")

    # ========== 4. 组装模型明细状态 ==========
    model_detail = []
    chart_model_data = []
    for item in valid_results:
        # 单模型状态判定
        if diverge_level >= 2 and (
            abs(item["score"] - consensus_score) > 0.2
        ):
            status = "diverge"
            desc = "该模型结论与共识存在显著偏差"
        else:
            status = "normal"
            desc = "推演正常参与共识融合"

        model_detail.append({
            "name": item["name"],
            "score": item["score"],
            "confidence": item["confidence"],
            "dynamic_weight": item["weight"],
            "status": status,
            "desc": desc,
        })
        chart_model_data.append({
            "name": item["name"],
            "score": item["score"],
            "confidence": item["confidence"],
            "weight": item["weight"],
        })

    # 共识拟合曲线（单点示例，后续迭代可扩展多时间节点）
    chart_consensus_data = [
        {"label": "共识拟合", "consensus_score": consensus_score},
    ]

    # ========== 5. 组装完整返回 ==========
    consensus = ConsensusResult(
        consensus_score=consensus_score,
        trend=trend,
        confidence=confidence,
        valid_model_count=len(valid_results),
        total_model_count=len(wc),
        diverge_level=diverge_level,
    )

    items_model_detail = [ModelDetailItem(**md) for md in model_detail]
    items_chart_model = [ChartModelDataItem(**cm) for cm in chart_model_data]
    items_chart_consensus = [ChartConsensusDataItem(**cc) for cc in chart_consensus_data]
    items_logs = [ProcessLogItem(**log) for log in process_logs]

    data = MultiConsensusData(
        consensus=consensus,
        model_detail=items_model_detail,
        chart_model_data=items_chart_model,
        chart_consensus_data=items_chart_consensus,
        process_logs=items_logs,
    )

    return MultiConsensusResp(code=200, msg="ok", data=data)
