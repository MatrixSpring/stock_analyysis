# -*- coding: utf-8 -*-
"""
============================================================================
扩展数据源模块 — 从 ai_mark 子系统融合
============================================================================

提供 data_provider/ 主线未覆盖的额外数据源：
  - GDELT 全球事件数据库（地缘风险/供应链中断监测）
  - RSS 多区域财经订阅（36氪/华尔街见闻/路透/彭博等）
  - Web 定向抓取（新浪财经/东方财富/财联社/雪球等）
  - Hotlist 热榜聚合（头条/百度/知乎/微博热搜）
  - FetcherRegistry 统一调度门面（分类/去重/情感标记）

设计原则：
  - 各 fetcher 实现 data_provider.base.BaseFetcher 接口
  - 统一标准化列名与 data_provider/base.py 的 STANDARD_COLUMNS 对齐
  - 可选依赖：无网络时自动降级，不影响主流程
"""

from data_provider.extended.registry import ExtendedFetcherRegistry

__all__ = ["ExtendedFetcherRegistry"]
