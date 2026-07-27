# -*- coding: utf-8 -*-
"""
申万行业 + 产业链标签数据同步模块

数据来源：
  - 离线 CSV（申万行业分类清单 + 产业链映射表）
  - Tushare API（行业分类接口，需 token）
  - akshare（行业分类补充）

标签体系：
  - industry_code: 申万三级行业代码 (如 SW640101)
  - l1/l2/l3: 一级/二级/三级行业名称
  - chain_tags: 产业链标签数组 (如 ["新能源产业链", "上游原材料"])
  - sector_tags: 概念板块标签

写入目标：MongoDB stock_industry 集合
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ============================================================
# 申万一级行业代码 → 产业链映射（静态表）
# ============================================================

SW_INDUSTRY_TO_CHAIN: Dict[str, List[str]] = {
    "农林牧渔": ["粮食安全产业链", "上游原材料"],
    "煤炭": ["传统能源产业链", "上游原材料"],
    "石油石化": ["传统能源产业链", "上游原材料", "化工产业链"],
    "钢铁": ["上游原材料", "基建产业链"],
    "有色金属": ["上游原材料", "新能源产业链（锂/钴/镍）"],
    "基础化工": ["化工产业链", "上游原材料"],
    "建筑材料": ["基建产业链"],
    "建筑装饰": ["基建产业链", "房地产产业链"],
    "电力设备": ["新能源产业链", "电力产业链"],
    "机械设备": ["高端制造产业链", "通用设备"],
    "国防军工": ["军工产业链", "高端制造产业链"],
    "汽车": ["新能源汽车产业链", "大消费"],
    "家用电器": ["大消费", "出口链"],
    "食品饮料": ["大消费", "白酒产业链"],
    "医药生物": ["医药产业链", "生物科技产业链"],
    "纺织服饰": ["大消费", "出口链"],
    "轻工制造": ["大消费"],
    "商贸零售": ["大消费", "电商产业链"],
    "社会服务": ["大消费"],
    "银行": ["金融产业链"],
    "非银金融": ["金融产业链"],
    "房地产": ["房地产产业链"],
    "电子": ["半导体产业链", "消费电子产业链", "AI算力产业链"],
    "计算机": ["AI算力产业链", "信创产业链", "数字经济产业链"],
    "传媒": ["AI应用产业链", "数字经济产业链"],
    "通信": ["AI算力产业链（光模块/CPO）", "数字经济产业链"],
    "公用事业": ["电力产业链"],
    "交通运输": ["供应链物流产业链", "出口链"],
    "环保": ["碳中和产业链"],
    "美容护理": ["大消费"],
    "综合": [],
}

# ============================================================
# 从 Tushare 获取申万行业分类
# ============================================================

def fetch_industry_from_tushare(token: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    通过 Tushare index_classify 接口获取申万行业分类。

    返回：[{"code": "600519", "industry_code": "SW340102", "l1": "食品饮料", ...}]
    """
    try:
        import tushare as ts

        ts_token = token or ""
        if not ts_token:
            return []

        pro = ts.pro_api(ts_token)
        # Tushare 申万行业分类接口
        df = pro.index_classify(level="L1", src="SW2021")
        if df is None or df.empty:
            return []

        results = []
        for _, row in df.iterrows():
            results.append({
                "code": str(row.get("ts_code", "")).split(".")[0],
                "industry_code": str(row.get("index_code", "")),
                "l1": str(row.get("industry_name", "")),
                "source": "tushare",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
        return results
    except ImportError:
        return []
    except Exception as e:
        logger.warning(f"[IndustryFetcher] Tushare fetch failed: {e}")
        return []


# ============================================================
# 从 akshare 获取行业归属
# ============================================================

def fetch_industry_from_akshare(stock_code: str) -> Optional[Dict[str, Any]]:
    """通过 akshare stock_individual_info_em 获取个股行业信息"""
    try:
        import akshare as ak

        info = ak.stock_individual_info_em(symbol=stock_code)
        if info is None or info.empty:
            return None

        info_dict = dict(zip(info["item"], info["value"]))
        industry = info_dict.get("行业", info_dict.get("industry", ""))

        if not industry:
            return None

        # 拆分行业层级
        parts = industry.replace("--", "-").replace("—", "-").split("-")

        return {
            "code": stock_code,
            "source": "akshare",
            "industry_raw": industry,
            "l1": parts[0] if len(parts) > 0 else "",
            "l2": parts[1] if len(parts) > 1 else "",
            "l3": parts[2] if len(parts) > 2 else "",
            "chain_tags": SW_INDUSTRY_TO_CHAIN.get(parts[0], []) if parts else [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    except ImportError:
        return None
    except Exception as e:
        logger.debug(f"[IndustryFetcher] akshare fetch failed for {stock_code}: {e}")
        return None


# ============================================================
# 标签绑定引擎（批量处理）
# ============================================================

def tag_stock_with_industry(stock_code: str,
                            industry_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    为单只股票绑定行业 + 产业链标签。

    Args:
        stock_code: 股票代码
        industry_data: 预获取的行业数据（可选，不传则自动从 akshare 获取）

    Returns:
        标签字典
    """
    if industry_data is None:
        industry_data = fetch_industry_from_akshare(stock_code)

    if not industry_data:
        return {
            "code": stock_code,
            "industry_code": "",
            "l1": "",
            "l2": "",
            "l3": "",
            "chain_tags": [],
            "tagged": False,
            "source": "none",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    # 查找产业链标签
    l1 = industry_data.get("l1", "")
    chain_tags = industry_data.get("chain_tags", [])
    if not chain_tags and l1:
        chain_tags = SW_INDUSTRY_TO_CHAIN.get(l1, [])

    return {
        "code": stock_code,
        "industry_code": industry_data.get("industry_code", ""),
        "l1": l1,
        "l2": industry_data.get("l2", ""),
        "l3": industry_data.get("l3", ""),
        "chain_tags": chain_tags,
        "tagged": bool(l1),
        "source": industry_data.get("source", "akshare"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def batch_tag_stocks(stock_list: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    批量为股票列表绑定行业标签。

    Returns:
        {stock_code: tag_dict, ...}
    """
    results = {}
    for i, code in enumerate(stock_list):
        try:
            results[code] = tag_stock_with_industry(code)
        except Exception as e:
            results[code] = {"code": code, "tagged": False, "error": str(e)}
        if i > 0 and i % 20 == 0:
            logger.info(f"[IndustryFetcher] Tagged {i}/{len(stock_list)} stocks")
    return results


def export_industry_tags_to_mongo(stock_list: List[str]) -> int:
    """
    批量标签绑定并写入 MongoDB。

    Returns:
        成功写入数
    """
    try:
        from src.data_storage import get_mongo
        mongo = get_mongo()
        if not mongo.db:
            return 0

        tags = batch_tag_stocks(stock_list)
        count = 0
        for code, tag_data in tags.items():
            if tag_data.get("tagged"):
                tag_data["dt"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if mongo.upsert_one("stock_industry", {"code": code}, tag_data):
                    count += 1

        logger.info(f"[IndustryFetcher] Exported {count}/{len(stock_list)} tags to MongoDB")
        return count
    except Exception as e:
        logger.error(f"[IndustryFetcher] MongoDB export failed: {e}")
        return 0


# ============================================================
# 标签查询工具（供选股/筛选使用）
# ============================================================

def get_stocks_by_industry(l1_name: str) -> List[str]:
    """按申万一级行业查询标的"""
    try:
        from src.data_storage import get_mongo
        mongo = get_mongo()
        docs = mongo.find_many("stock_industry", {"l1": l1_name})
        return [d["code"] for d in docs if d.get("code")]
    except Exception:
        return []


def get_stocks_by_chain_tag(chain_tag: str) -> List[str]:
    """按产业链标签查询标的"""
    try:
        from src.data_storage import get_mongo
        mongo = get_mongo()
        docs = mongo.find_many("stock_industry", {"chain_tags": chain_tag})
        return [d["code"] for d in docs if d.get("code")]
    except Exception:
        return []


def format_industry_tags_for_prompt(stock_code: str) -> str:
    """
    获取单只股票的行业标签，格式化为 Agent prompt 文本。

    Returns:
        如 "食品饮料 | 白酒产业链 | 大消费" 或空字符串
    """
    tags = tag_stock_with_industry(stock_code)
    if not tags.get("tagged"):
        return ""

    parts = []
    for key in ("l1", "l2", "l3"):
        if tags.get(key):
            parts.append(tags[key])
    if tags.get("chain_tags"):
        parts.append(" → ".join(tags["chain_tags"]))

    return " | ".join(parts)
