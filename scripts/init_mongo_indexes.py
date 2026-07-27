#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MongoDB 初始化索引脚本 — DSA 采集模块落地配套

用法：
  python scripts/init_mongo_indexes.py                 # 创建所有索引
  python scripts/init_mongo_indexes.py --drop          # 删除旧索引后重建
  python scripts/init_mongo_indexes.py --dry-run       # 仅打印，不执行
"""

import argparse
import logging
import sys
from pathlib import Path

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mongo_init")

# ============================================================
# 集合定义
# ============================================================

COLLECTIONS = {
    "stock_daily": "日线 K 线",
    "stock_minute": "分时/分钟 K 线",
    "stock_chip": "筹码分布",
    "stock_fundamental": "基本面财务数据",
    "stock_realtime": "实时行情快照",
    "stock_industry": "申万行业+产业链标签",
    "stock_news": "个股新闻资讯",
    "stock_sentiment": "社区舆情评论",
    "stock_sentiment_agg": "舆情聚合指标",
    "crawl_metadata": "采集元数据",
}

# ============================================================
# 索引定义
# ============================================================

INDEXES = {
    "stock_daily": [
        ({"code": 1, "dt": -1}, {"unique": True, "name": "idx_code_dt"}),
        ({"market": 1, "dt": -1}, {"name": "idx_market_dt"}),
        ({"dt": -1}, {"name": "idx_dt"}),
    ],
    "stock_minute": [
        ({"code": 1, "dt": 1}, {"unique": True, "name": "idx_code_minute"}),
        ({"dt": -1}, {"name": "idx_minute_dt"}),
    ],
    "stock_chip": [
        ({"code": 1, "dt": -1}, {"unique": True, "name": "idx_chip_code_dt"}),
    ],
    "stock_fundamental": [
        ({"code": 1, "report_period": -1}, {"unique": True, "name": "idx_fund_code_report"}),
        ({"report_period": -1}, {"name": "idx_fund_report"}),
        ({"quality": 1}, {"name": "idx_fund_quality"}),
    ],
    "stock_realtime": [
        ({"code": 1}, {"unique": True, "name": "idx_rt_code"}),
        ({"market": 1}, {"name": "idx_rt_market"}),
    ],
    "stock_industry": [
        ({"code": 1}, {"unique": True, "name": "idx_ind_code"}),
        ({"l1": 1, "industry_code": 1}, {"name": "idx_ind_l1_code"}),
        ({"chain_tags": 1}, {"name": "idx_ind_chain"}),
        ({"tagged": 1}, {"name": "idx_ind_tagged"}),
    ],
    "stock_news": [
        ({"code": 1, "publish_time": -1}, {"name": "idx_news_code_time"}),
        ({"news_level": 1, "publish_time": -1}, {"name": "idx_news_level_time"}),
        ({"source_platform": 1}, {"name": "idx_news_platform"}),
    ],
    "stock_sentiment": [
        ({"code": 1, "publish_time": -1}, {"name": "idx_sent_code_time"}),
        ({"source_platform": 1, "publish_time": -1}, {"name": "idx_sent_platform"}),
        ({"sentiment_score": 1}, {"name": "idx_sent_score"}),
    ],
    "stock_sentiment_agg": [
        ({"code": 1, "time_window": 1}, {"unique": True, "name": "idx_agg_code_window"}),
        ({"crawl_at": -1}, {"name": "idx_agg_time"}),
    ],
    "crawl_metadata": [
        ({"code": 1, "data_type": 1, "source": 1}, {"name": "idx_crawl_code_type_src"}),
        ({"source": 1, "status": 1}, {"name": "idx_crawl_source_status"}),
        ({"crawl_at": -1}, {"name": "idx_crawl_time"}),
        ({"source": 1, "status": 1, "crawl_at": -1}, {"name": "idx_crawl_health"}),
    ],
}


def connect_mongo(uri: str, db_name: str):
    """连接 MongoDB"""
    try:
        from pymongo import MongoClient
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        db = client[db_name]
        logger.info(f"MongoDB connected: {db_name}")
        return client, db
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        return None, None


def create_indexes(db, dry_run: bool = False):
    """创建所有集合的索引"""
    created = 0
    skipped = 0
    errors = 0

    for coll_name, indexes in INDEXES.items():
        label = COLLECTIONS.get(coll_name, coll_name)

        for keys, options in indexes:
            idx_name = options.get("name", str(keys))
            if dry_run:
                logger.info(f"[DRY-RUN] {coll_name} ({label}): {idx_name} → {keys}")
                created += 1
                continue

            try:
                db[coll_name].create_index(list(keys.items()), **options)
                logger.info(f"[OK] {coll_name}.{idx_name}")
                created += 1
            except Exception as e:
                logger.warning(f"[SKIP] {coll_name}.{idx_name}: {e}")
                skipped += 1

    return created, skipped, errors


def drop_indexes(db, dry_run: bool = False):
    """删除所有非 _id 索引"""
    for coll_name in COLLECTIONS:
        if dry_run:
            logger.info(f"[DRY-RUN] Would drop indexes on {coll_name}")
            continue
        try:
            db[coll_name].drop_indexes()
            logger.info(f"[DROP] {coll_name} indexes cleared")
        except Exception as e:
            logger.debug(f"[DROP] {coll_name}: {e}")


def print_schema_summary():
    """打印 Schema 摘要"""
    print()
    print("=" * 60)
    print("  MongoDB 集合 Schema 摘要")
    print("=" * 60)
    for coll_name, label in COLLECTIONS.items():
        idx_list = INDEXES.get(coll_name, [])
        print(f"\n  {coll_name}  ─ {label}")
        for keys, opts in idx_list:
            keys_str = ", ".join(f"{k}({'+' if v > 0 else '-'})" for k, v in keys.items())
            unique = "UNIQUE" if opts.get("unique") else ""
            print(f"    {opts.get('name', keys_str):30s} {keys_str:30s} {unique}")


def main():
    parser = argparse.ArgumentParser(description="DSA MongoDB 索引初始化")
    parser.add_argument("--uri", default="mongodb://localhost:27017", help="MongoDB URI")
    parser.add_argument("--db", default="dsa_stock", help="数据库名")
    parser.add_argument("--drop", action="store_true", help="删除旧索引后重建")
    parser.add_argument("--dry-run", action="store_true", help="仅打印，不执行")
    args = parser.parse_args()

    print_schema_summary()
    print()

    if args.dry_run:
        logger.info("=== DRY RUN MODE ===")

    client, db = connect_mongo(args.uri, args.db)
    if client is None:
        logger.error("Cannot connect to MongoDB. Is it running?")
        logger.info("Install: brew install mongodb-community")
        logger.info("Start: brew services start mongodb-community")
        sys.exit(1)

    if args.drop:
        drop_indexes(db, dry_run=args.dry_run)

    created, skipped, errors = create_indexes(db, dry_run=args.dry_run)
    print()
    logger.info(f"Done: {created} created, {skipped} skipped, {errors} errors")

    client.close()


if __name__ == "__main__":
    main()
