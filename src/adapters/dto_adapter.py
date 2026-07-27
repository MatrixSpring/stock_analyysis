# -*- coding: utf-8 -*-
"""
===================================
DTO 适配器 — DTOAdapter
===================================

职责：
1. 新旧字段映射：自动翻译旧版字段名到新版数据结构
2. 类型转换：确保输出字段类型与调用方期望一致
3. 字段补齐/裁剪：旧版缺失字段填默认值，新版多余字段可裁剪
4. 向后兼容：所有旧版 API 数据结构通过本适配器输出
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# ============================================================
# 字段映射表
# ============================================================

# K线数据：旧版 → 新版字段映射
KLINE_FIELD_MAP: Dict[str, str] = {
    # 旧版字段名         新版字段名
    "date": "date",
    "trade_date": "date",
    "open_price": "open",
    "open": "open",
    "high_price": "high",
    "high": "high",
    "low_price": "low",
    "low": "low",
    "close_price": "close",
    "close": "close",
    "vol": "volume",
    "volume": "volume",
    "turnover": "amount",
    "amount": "amount",
    "change_pct": "pct_chg",
    "pct_chg": "pct_chg",
    "pct_change": "pct_chg",
    "change": "change",
    "amplitude": "amplitude",
    "turnover_rate": "turnover_rate",
}

# 股票基础信息
STOCK_FIELD_MAP: Dict[str, str] = {
    "code": "code",
    "stock_code": "code",
    "symbol": "code",
    "name": "name",
    "stock_name": "name",
    "market": "market",
    "region": "market",
    "industry": "industry",
    "sector": "industry",
    "list_date": "list_date",
    "ipo_date": "list_date",
    "total_shares": "total_shares",
    "float_shares": "float_shares",
    "circulating_shares": "float_shares",
}

# 资金流向
CAPITAL_FLOW_MAP: Dict[str, str] = {
    "main_net_inflow": "main_net_inflow",
    "super_large_net": "super_large_net_inflow",
    "large_net": "large_net_inflow",
    "medium_net": "medium_net_inflow",
    "small_net": "small_net_inflow",
    "main_net_ratio": "main_net_ratio",
    "north_bound": "north_bound_inflow",
    "north_net": "north_bound_inflow",
}

# 回测结果
BACKTEST_FIELD_MAP: Dict[str, str] = {
    "stock": "stock_code",
    "analysis_date": "analysis_date",
    "ai_prediction": "ai_prediction",
    "actual_performance": "actual_performance",
    "window_return": "window_return",
    "direction_match": "direction_match",
    "accuracy": "accuracy",
}

# 反向映射（新版 → 旧版兼容输出）
REVERSE_KLINE_MAP: Dict[str, str] = {v: k for k, v in KLINE_FIELD_MAP.items()}


# ============================================================
# 默认值配置
# ============================================================

# 各字段的默认值（旧版字段缺失时填充）
FIELD_DEFAULTS: Dict[str, Any] = {
    "open": 0.0,
    "high": 0.0,
    "low": 0.0,
    "close": 0.0,
    "volume": 0,
    "amount": 0.0,
    "pct_chg": 0.0,
    "change": 0.0,
    "amplitude": 0.0,
    "turnover_rate": 0.0,
    "main_net_inflow": 0.0,
    "north_bound_inflow": 0.0,
    "name": "",
    "industry": "",
    "list_date": "",
}


@dataclass
class AdapterConfig:
    """适配器配置"""
    field_map: Dict[str, str] = field(default_factory=dict)
    defaults: Dict[str, Any] = field(default_factory=dict)
    strict: bool = False  # True = 严格模式：旧字段不存在则报错
    drop_unknown: bool = False  # True = 丢弃新版多余字段
    target_schema: Optional[List[str]] = None  # 限定输出字段列表


class DTOAdapter:
    """
    数据格式适配器。

    使用方式：
        adapter = DTOAdapter.for_kline()
        new_data = adapter.to_new_format(old_data)
        old_data = adapter.to_legacy_format(new_data)
    """

    def __init__(self, config: AdapterConfig):
        self._config = config

    # ============================================================
    # 工厂方法
    # ============================================================

    @classmethod
    def for_kline(cls) -> "DTOAdapter":
        """K线数据适配器"""
        return cls(AdapterConfig(
            field_map=KLINE_FIELD_MAP,
            defaults={k: v for k, v in FIELD_DEFAULTS.items()
                      if k in set(KLINE_FIELD_MAP.values())},
        ))

    @classmethod
    def for_stock_info(cls) -> "DTOAdapter":
        """股票基础信息适配器"""
        return cls(AdapterConfig(
            field_map=STOCK_FIELD_MAP,
            defaults={"name": "", "industry": "", "market": "", "list_date": ""},
        ))

    @classmethod
    def for_capital_flow(cls) -> "DTOAdapter":
        """资金流向适配器"""
        return cls(AdapterConfig(
            field_map=CAPITAL_FLOW_MAP,
            defaults={
                "main_net_inflow": 0.0,
                "super_large_net_inflow": 0.0,
                "large_net_inflow": 0.0,
                "medium_net_inflow": 0.0,
                "small_net_inflow": 0.0,
                "north_bound_inflow": 0.0,
            },
        ))

    @classmethod
    def for_backtest(cls) -> "DTOAdapter":
        """回测结果适配器"""
        return cls(AdapterConfig(
            field_map=BACKTEST_FIELD_MAP,
            defaults={},
        ))

    @classmethod
    def custom(cls, field_map: Dict[str, str], defaults: Optional[Dict[str, Any]] = None) -> "DTOAdapter":
        """自定义适配器"""
        return cls(AdapterConfig(field_map=field_map, defaults=defaults or {}))

    # ============================================================
    # 核心转换方法
    # ============================================================

    def to_new_format(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        旧版格式 → 新版格式。

        旧字段通过 field_map 映射到新字段名，缺失字段填充默认值。
        """
        return self._convert(data, self._config.field_map, self._config.defaults)

    def to_legacy_format(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        新版格式 → 旧版格式（向后兼容）。

        用于新版 API 输出给旧版前端/客户端。
        """
        reverse_map = {v: k for k, v in self._config.field_map.items()}
        return self._convert(data, reverse_map, self._config.defaults)

    def to_new_format_batch(self, data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量旧版 → 新版"""
        return [self.to_new_format(d) for d in data_list]

    def to_legacy_format_batch(self, data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量新版 → 旧版"""
        return [self.to_legacy_format(d) for d in data_list]

    def adapt_value(self, old_key: str, value: Any) -> Tuple[str, Any]:
        """将单个旧字段名和值转换为新版"""
        new_key = self._config.field_map.get(old_key, old_key)
        return new_key, value

    def adapt_series(self, series: Dict[str, Any]) -> Dict[str, Any]:
        """
        智能适配：自动检测是旧版还是新版格式并转换。
        如果大部分字段已匹配新版命名 → 不需要转换。
        """
        new_keys = set(self._config.field_map.values())
        overlap = sum(1 for k in series if k in new_keys)
        legacy_overlap = sum(1 for k in series if k in self._config.field_map)

        if overlap >= legacy_overlap:
            return series  # 已是新版格式
        return self.to_new_format(series)

    # ============================================================
    # Pandas DataFrame 适配
    # ============================================================

    def adapt_dataframe(self, df: "pd.DataFrame") -> "pd.DataFrame":  # noqa: F821
        """
        适配 DataFrame：重命名列 + 补齐缺失列。
        自动检测列名是旧版还是新版并转换。
        """
        import pandas as pd

        result = df.copy()
        new_columns = set(self._config.field_map.values())
        current_columns = set(result.columns)

        # 检测格式方向
        if new_columns.intersection(current_columns):
            # 部分或全部已是新版列名 → 补齐缺失列
            for col in new_columns:
                if col not in current_columns:
                    result[col] = self._config.defaults.get(col, 0.0)
        else:
            # 旧版格式 → 重命名
            rename_dict = {
                old: new
                for old, new in self._config.field_map.items()
                if old in current_columns
            }
            result = result.rename(columns=rename_dict)
            # 补齐缺失列
            for col in new_columns:
                if col not in result.columns:
                    result[col] = self._config.defaults.get(col, 0.0)

        # 裁剪多余列
        if self._config.drop_unknown:
            result = result[list(new_columns)]

        # 限定输出列
        if self._config.target_schema:
            result = result[self._config.target_schema]

        return result

    # ============================================================
    # 内部方法
    # ============================================================

    def _convert(
        self,
        data: Dict[str, Any],
        field_map: Dict[str, str],
        defaults: Dict[str, Any],
    ) -> Dict[str, Any]:
        """执行字段映射转换"""
        result: Dict[str, Any] = {}

        # 1. 映射已有字段
        for old_key, value in data.items():
            new_key = field_map.get(old_key, old_key if not self._config.strict else None)
            if new_key is None:
                logger.warning(f"[DTOAdapter] 字段 {old_key} 未找到映射，strict 模式丢弃")
                continue
            result[new_key] = value

        # 2. 补齐缺失字段的默认值
        for target_key in set(field_map.values()):
            if target_key not in result:
                result[target_key] = defaults.get(target_key, None)

        # 3. 裁剪
        if self._config.drop_unknown:
            allowed = set(field_map.values())
            result = {k: v for k, v in result.items() if k in allowed}

        # 4. 限定
        if self._config.target_schema:
            result = {k: result.get(k) for k in self._config.target_schema}

        return result
