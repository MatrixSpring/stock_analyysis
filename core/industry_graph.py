# -*- coding: utf-8 -*-
"""
===================================
产业链图谱引擎 — core/industry_graph.py
===================================

行业景气度、上下游传导、事件冲击推演、成分股查询。

使用方式：
    from core.industry_graph import IndustryGraphEngine
    engine = IndustryGraphEngine()
    chain = engine.get_industry_chain("光伏")
    stocks = engine.get_related_stocks("光伏", direction="downstream")
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from core.utils import safe_execute, clamp

logger = logging.getLogger(__name__)

# 内置产业链拓扑数据（可替换为外部 JSON/DB 加载）
_INDUSTRY_CHAINS: Dict[str, Dict] = {
    "光伏": {
        "name": "光伏",
        "upstream": ["硅料", "硅片", "银浆", "光伏玻璃", "EVA胶膜"],
        "midstream": ["电池片", "组件", "逆变器", "支架"],
        "downstream": ["电站运营", "分布式光伏", "储能系统"],
        "key_stocks": {
            "硅料": ["600438", "601012"],
            "硅片": ["601012", "002459"],
            "电池片": ["600438", "002459"],
            "组件": ["601012", "688599"],
            "逆变器": ["300274", "688390"],
            "电站运营": ["601615", "000591"],
        },
        "capital_flow_score": 6.5,
    },
    "新能源汽车": {
        "name": "新能源汽车",
        "upstream": ["锂矿", "钴矿", "正极材料", "负极材料", "电解液", "隔膜"],
        "midstream": ["动力电池", "电机电控", "热管理"],
        "downstream": ["整车制造", "充电桩", "电池回收"],
        "key_stocks": {
            "锂矿": ["002460", "002466"],
            "正极材料": ["300750", "688005"],
            "电解液": ["002709", "300037"],
            "动力电池": ["300750", "002074"],
            "整车制造": ["002594", "601633", "000625"],
            "充电桩": ["300001", "002276"],
        },
        "capital_flow_score": 7.2,
    },
    "半导体": {
        "name": "半导体",
        "upstream": ["硅片", "光刻胶", "电子气体", "靶材"],
        "midstream": ["芯片设计", "晶圆制造", "封装测试"],
        "downstream": ["消费电子", "服务器", "汽车电子", "AI芯片"],
        "key_stocks": {
            "芯片设计": ["603986", "688981"],
            "晶圆制造": ["688981", "002371"],
            "封装测试": ["002156", "600584"],
            "消费电子": ["002475", "601138"],
            "AI芯片": ["688256", "300474"],
        },
        "capital_flow_score": 8.0,
    },
    "医药": {
        "name": "医药",
        "upstream": ["原料药", "中间体", "药用辅料"],
        "midstream": ["化学制药", "生物制药", "中药", "医疗器械"],
        "downstream": ["医院", "药店", "互联网医疗"],
        "key_stocks": {
            "化学制药": ["600276", "000963"],
            "生物制药": ["300122", "688180"],
            "中药": ["600085", "000538"],
            "医疗器械": ["300760", "688029"],
            "医院": ["600763", "300015"],
        },
        "capital_flow_score": 5.8,
    },
    "白酒": {
        "name": "白酒",
        "upstream": ["高粱", "小麦", "包装材料"],
        "midstream": ["基酒生产", "勾调陈酿", "品牌运营"],
        "downstream": ["高端白酒", "次高端", "大众酒", "电商渠道"],
        "key_stocks": {
            "高端白酒": ["600519", "000858", "000568"],
            "次高端": ["600809", "002304"],
            "大众酒": ["000596", "600559"],
        },
        "capital_flow_score": 4.2,
    },
}


class IndustryGraphEngine:
    """
    产业链图谱业务引擎。

    支持：产业链查询、景气度打分、传导强度计算、成分股筛选
    """

    def __init__(self):
        self.chains = _INDUSTRY_CHAINS
        self._load_custom_data()

    def _load_custom_data(self):
        """从外部文件加载自定义产业链数据"""
        try:
            import json
            from pathlib import Path
            custom_path = Path("data/industry_chains.json")
            if custom_path.exists():
                custom = json.loads(custom_path.read_text(encoding="utf-8"))
                self.chains.update(custom)
                logger.info(f"[IndustryGraph] 加载自定义产业链: {len(custom)} 个")
        except Exception as e:
            logger.debug(f"[IndustryGraph] 无自定义数据: {e}")

    # ---- 产业链查询 ----

    def get_industry_chain(self, industry: str) -> Optional[Dict]:
        """获取完整产业链拓扑"""
        return self.chains.get(industry)

    def list_industries(self) -> List[str]:
        """列出所有已加载产业链"""
        return list(self.chains.keys())

    def get_chain_summary(self, industry: str) -> Dict:
        """
        产业链概要：上下游节点数 + 成分股数 + 资金热度。

        Returns:
            {"industry": str, "node_count": int, "stock_count": int, "capital_score": float}
        """
        chain = self.chains.get(industry)
        if not chain:
            return {"industry": industry, "error": "产业链不存在"}

        node_count = (
            len(chain.get("upstream", []))
            + len(chain.get("midstream", []))
            + len(chain.get("downstream", []))
        )
        stock_count = sum(len(v) for v in chain.get("key_stocks", {}).values())
        return {
            "industry": industry,
            "node_count": node_count,
            "stock_count": stock_count,
            "capital_score": chain.get("capital_flow_score", 0),
            "upstream": chain.get("upstream", []),
            "midstream": chain.get("midstream", []),
            "downstream": chain.get("downstream", []),
        }

    # ---- 成分股查询 ----

    def get_related_stocks(
        self, industry: str, direction: str = "all"
    ) -> List[Dict[str, str]]:
        """
        获取产业链成分股。

        Args:
            industry: 产业链名称
            direction: upstream/midstream/downstream/all

        Returns:
            [{"code": str, "name": str, "segment": str}]
        """
        chain = self.chains.get(industry)
        if not chain:
            return []

        stocks = []
        key_stocks = chain.get("key_stocks", {})

        segments = {
            "upstream": chain.get("upstream", []),
            "midstream": chain.get("midstream", []),
            "downstream": chain.get("downstream", []),
        }

        for seg_name, node_list in segments.items():
            if direction != "all" and seg_name != direction:
                continue
            for node in node_list:
                codes = key_stocks.get(node, [])
                for code in codes:
                    stocks.append({
                        "code": code,
                        "segment": node,
                        "direction": seg_name,
                    })

        return stocks

    def get_stocks_by_segment(self, industry: str, segment: str) -> List[str]:
        """按细分环节获取股票代码列表"""
        chain = self.chains.get(industry)
        if not chain:
            return []
        return chain.get("key_stocks", {}).get(segment, [])

    # ---- 景气度 ----

    def calc_industry_sentiment(self, industries: List[str]) -> pd.DataFrame:
        """
        批量行业景气度打分。

        基于：资金流向评分 + 行业涨跌幅联动 + 事件冲击。

        Returns:
            DataFrame: industry, sentiment_score, capital_score, risk_level
        """
        rows = []
        for ind in industries:
            chain = self.chains.get(ind, {})
            capital = chain.get("capital_flow_score", 5)
            sentiment = clamp(capital / 10, 0.1, 0.9)
            risk = "低" if sentiment > 0.6 else ("中" if sentiment > 0.4 else "高")
            rows.append({
                "industry": ind,
                "sentiment_score": round(sentiment, 2),
                "capital_score": capital,
                "risk_level": risk,
            })
        return pd.DataFrame(rows)

    # ---- 传导强度 ----

    def calculate_transmission(
        self, source_industry: str, event_strength: float = 5.0
    ) -> Dict[str, Any]:
        """
        计算事件冲击沿产业链的传导强度。

        上游冲击 → 中游衰减 20% → 下游衰减 40%

        Args:
            source_industry: 冲击源产业链
            event_strength: 事件强度 1~10

        Returns:
            {"direct": float, "upstream_impact": float, "midstream_impact": float, "downstream_impact": float}
        """
        chain = self.chains.get(source_industry)
        if not chain:
            return {"error": "产业链不存在"}

        direct = event_strength
        upstream_impact = event_strength * 0.9  # 上游反馈强
        midstream_impact = event_strength * 0.8   # 中游衰减 20%
        downstream_impact = event_strength * 0.6  # 下游衰减 40%

        return {
            "direct": round(direct, 2),
            "upstream_impact": round(upstream_impact, 2),
            "midstream_impact": round(midstream_impact, 2),
            "downstream_impact": round(downstream_impact, 2),
            "affected_sectors": {
                "upstream": chain.get("upstream", []),
                "midstream": chain.get("midstream", []),
                "downstream": chain.get("downstream", []),
            },
        }

    # ---- 传导选股 ----

    def screen_by_transmission(
        self, industry: str, event_strength: float = 5.0, direction: str = "all"
    ) -> List[Dict]:
        """
        根据事件传导方向自动选股。

        Args:
            industry: 冲击源产业链
            event_strength: 事件强度 1~10
            direction: 传导方向 (upstream/midstream/downstream/all)

        Returns:
            成分股列表，附带传导强度
        """
        transmission = self.calculate_transmission(industry, event_strength)
        stocks = self.get_related_stocks(industry, direction)

        impact_map = {
            "upstream": transmission["upstream_impact"],
            "midstream": transmission["midstream_impact"],
            "downstream": transmission["downstream_impact"],
        }

        result = []
        for s in stocks:
            impact = impact_map.get(s["direction"], event_strength * 0.5)
            result.append({
                **s,
                "transmission_impact": round(impact, 2),
                "confidence": "高" if impact > 6 else ("中" if impact > 3 else "低"),
            })

        result.sort(key=lambda x: x["transmission_impact"], reverse=True)
        return result


# 全局单例
_industry_engine: Optional[IndustryGraphEngine] = None


def get_industry_engine() -> IndustryGraphEngine:
    global _industry_engine
    if _industry_engine is None:
        _industry_engine = IndustryGraphEngine()
    return _industry_engine
