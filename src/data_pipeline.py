# -*- coding: utf-8 -*-
"""
===================================
量化数据预处理流水线 — DataPipeline
===================================

对齐 Qlib/QuantMind 工业标准:
1. 缺失值处理：行业均值/前值填充，连续缺失>3标记无效
2. 去极值 (MAD): 中位数绝对偏差法，剔除3倍MAD异常值
3. Z-score 标准化
4. 行业中性化 + 市值中性化
5. 固化入库作为回测/选股唯一数据源
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class DataPipeline:
    """量化数据预处理流水线"""

    def __init__(self):
        self._steps_applied: List[str] = []
        self._stats: Dict[str, Any] = {}

    # ============================================================
    # 步骤1: 缺失值处理
    # ============================================================

    def fill_missing(
        self, data: np.ndarray,
        industry_means: Optional[np.ndarray] = None,
        max_consecutive_nan: int = 3,
    ) -> np.ndarray:
        """
        缺失值处理：行业均值填充 + 前值填充 + 连续缺失标记。

        Args:
            data: (T, N) 矩阵
            industry_means: (N,) 行业均值
            max_consecutive_nan: 连续缺失超过此值标记无效

        Returns:
            填充后的矩阵
        """
        result = data.copy().astype(np.float64)
        invalid_mask = np.zeros(result.shape[1], dtype=bool)
        n_rows, n_cols = result.shape

        for col in range(n_cols):
            col_data = result[:, col]
            nan_mask = np.isnan(col_data)

            # 连续缺失检测
            consecutive = 0
            for i in range(n_rows):
                if nan_mask[i]:
                    consecutive += 1
                    if consecutive > max_consecutive_nan:
                        invalid_mask[col] = True
                        break
                else:
                    consecutive = 0

            if invalid_mask[col]:
                continue

            # 前值填充
            last_valid = 0.0
            for i in range(n_rows):
                if np.isnan(col_data[i]):
                    col_data[i] = last_valid
                else:
                    last_valid = col_data[i]

            # 开头NaN用行业均值
            if industry_means is not None and col < len(industry_means):
                first_nan = np.isnan(col_data[:1]).any()
                if first_nan:
                    col_data[0] = industry_means[col]
            else:
                col_data[np.isnan(col_data)] = 0.0

            result[:, col] = col_data

        self._steps_applied.append("fill_missing")
        self._stats["fill_missing"] = {
            "nan_count": int(np.sum(np.isnan(data))),
            "invalid_columns": int(np.sum(invalid_mask)),
        }
        logger.info(
            f"[DataPipeline] 缺失值处理: {self._stats['fill_missing']['nan_count']} NaN, "
            f"{self._stats['fill_missing']['invalid_columns']} 列无效"
        )
        return result

    # ============================================================
    # 步骤2: 去极值 (MAD)
    # ============================================================

    def remove_outliers(self, data: np.ndarray, mad_multiplier: float = 3.0) -> np.ndarray:
        """
        MAD 去极值：|x - median| > multiplier * MAD → 截断。

        Args:
            data: (T, N) 矩阵
            mad_multiplier: MAD 倍数（默认3）

        Returns:
            去极值后的矩阵
        """
        result = data.copy()
        n_cols = result.shape[1]
        clipped_count = 0

        for col in range(n_cols):
            col_data = result[:, col]
            valid = col_data[~np.isnan(col_data)]
            if len(valid) < 10:
                continue

            median = np.median(valid)
            mad = np.median(np.abs(valid - median)) or 1e-8

            upper = median + mad_multiplier * mad
            lower = median - mad_multiplier * mad

            above = col_data > upper
            below = col_data < lower
            clipped_count += int(np.sum(above)) + int(np.sum(below))

            col_data[above] = upper
            col_data[below] = lower
            result[:, col] = col_data

        self._steps_applied.append("remove_outliers")
        self._stats["remove_outliers"] = {"clipped_count": clipped_count}
        logger.info(f"[DataPipeline] 去极值: {clipped_count} 个值被截断")
        return result

    # ============================================================
    # 步骤3: Z-score 标准化
    # ============================================================

    def zscore_normalize(self, data: np.ndarray) -> np.ndarray:
        """Z-score 标准化：(x - mean) / std"""
        result = data.copy()
        n_cols = result.shape[1]

        for col in range(n_cols):
            col_data = result[:, col]
            valid = col_data[~np.isnan(col_data)]
            if len(valid) < 10:
                continue

            mean = np.mean(valid)
            std = np.std(valid) or 1e-8
            result[:, col] = (col_data - mean) / std

        self._steps_applied.append("zscore")
        logger.info("[DataPipeline] Z-score 标准化完成")
        return result

    # ============================================================
    # 步骤4: 中性化
    # ============================================================

    def neutralize(
        self, data: np.ndarray,
        industry_labels: Optional[np.ndarray] = None,
        market_caps: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        行业中性化 + 市值中性化。

        方法：截面回归取残差
          factor_i = β_industry * industry_dummy + β_cap * log(market_cap) + ε_i
          中性化后 = ε_i

        Args:
            data: (N,) 因子值（截面）
            industry_labels: (N,) 行业标签
            market_caps: (N,) 市值

        Returns:
            中性化后的因子值
        """
        result = data.copy()
        n = len(data)

        if n < 10:
            return result

        valid = ~np.isnan(data)
        if not valid.any():
            return result

        # 构建设计矩阵
        X_list = [np.ones(n)[valid]]  # intercept

        if industry_labels is not None:
            industries = np.unique(industry_labels[valid])
            for ind in industries:
                X_list.append((industry_labels == ind).astype(float)[valid])
            # Drop first dummy
            if len(X_list) > 2:
                X_list = X_list[:1] + X_list[2:]

        if market_caps is not None:
            log_cap = np.log(np.maximum(market_caps, 1.0))
            X_list.append(log_cap[valid])

        X = np.column_stack(X_list) if len(X_list) > 1 else X_list[0].reshape(-1, 1)
        y = data[valid]

        try:
            # OLS: β = (X'X)^-1 X'y
            beta = np.linalg.lstsq(X, y, rcond=None)[0]
            fitted = X @ beta
            residuals = y - fitted
            result[valid] = residuals
        except np.linalg.LinAlgError:
            logger.warning("[DataPipeline] 中性化失败（矩阵不可逆），返回原始值")

        self._steps_applied.append("neutralize")
        logger.info("[DataPipeline] 行业+市值中性化完成")
        return result

    # ============================================================
    # 全流水线
    # ============================================================

    def run(
        self, data: np.ndarray,
        industry_means: Optional[np.ndarray] = None,
        industry_labels: Optional[np.ndarray] = None,
        market_caps: Optional[np.ndarray] = None,
        skip_neutralize: bool = False,
    ) -> np.ndarray:
        """执行完整数据预处理流水线"""
        result = self.fill_missing(data, industry_means)
        result = self.remove_outliers(result)
        result = self.zscore_normalize(result)
        if not skip_neutralize and (industry_labels is not None or market_caps is not None):
            for i in range(result.shape[1]):
                col = result[:, i].copy()
                result[:, i] = self.neutralize(
                    col, industry_labels, market_caps,
                )
        logger.info(f"[DataPipeline] 全流水线完成: {' → '.join(self._steps_applied)}")
        return result

    def get_summary(self) -> Dict[str, Any]:
        return {"steps": self._steps_applied, "stats": self._stats}
