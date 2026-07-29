#!/usr/bin/env python3
"""
===================================
数据维护脚本 — scripts/data_maintenance.py
===================================

一键执行：
1. 数据库索引创建
2. 脏数据清洗（默认 dry_run，加 --apply 执行删除）
3. 缓存刷新
4. 增量更新检查

使用：
    python scripts/data_maintenance.py              # 诊断模式
    python scripts/data_maintenance.py --apply      # 执行修复
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def main():
    parser = argparse.ArgumentParser(description="数据维护工具")
    parser.add_argument("--apply", action="store_true", help="执行修复（默认 dry-run）")
    parser.add_argument("--stock", type=str, help="检查指定股票的增量更新状态")
    args = parser.parse_args()

    print("=" * 60)
    print("  DSA 数据维护工具")
    print("=" * 60)

    # 1. 索引
    print("\n[1/4] 数据库索引...")
    from core.data_optimizer import ensure_all_indexes
    ensure_all_indexes()

    # 2. 清洗
    print("\n[2/4] 脏数据清洗...")
    from core.data_optimizer import clean_abnormal_prices
    stats = clean_abnormal_prices(dry_run=not args.apply)
    mode = "DRY-RUN" if not args.apply else "已执行"
    print(f"  [{mode}] 异常行: {stats['abnormal_rows']}, 停牌行: {stats['suspended_rows']}, 清理: {stats['cleaned_rows']}")

    # 3. 增量更新
    print("\n[3/4] 增量更新检查...")
    if args.stock:
        from datetime import datetime
        from core.data_optimizer import get_missing_dates
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - __import__("datetime").timedelta(days=30)).strftime("%Y-%m-%d")
        missing = get_missing_dates(Path("data/dsa_workspace.db"), args.stock, start, end)
        print(f"  {args.stock}: 缺失 {len(missing)} 天数据")
        if missing and len(missing) <= 10:
            print(f"  缺失日期: {', '.join(missing)}")
    else:
        print("  跳过（使用 --stock 指定代码进行检查）")

    # 4. 缓存
    print("\n[4/4] 内存缓存...")
    from core.data_optimizer import flush_cache
    flush_cache()

    print("\n" + "=" * 60)
    print("  维护完成。使用 --apply 执行实际修改。")
    print("=" * 60)


if __name__ == "__main__":
    main()
