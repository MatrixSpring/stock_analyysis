# -*- coding: utf-8 -*-
"""
============================================================================
ETL 管道模块 — 从 ai_mark 子系统融合并标准化

提供统一的数据抽取→转换→加载管道：
  - DataTransformer: 多源数据标准化转换器
  - ETL Pipeline: 抓取→转换→入库三层抽象

与 data_provider/base.py 的 STANDARD_COLUMNS 对齐，对外提供统一接口。

原始来源：ai_mark/integrations/financial_data/pipeline.py
"""

from src.etl.pipeline import DataTransformer, ETLPipeline

__all__ = ["DataTransformer", "ETLPipeline"]
