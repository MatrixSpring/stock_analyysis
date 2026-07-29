#!/usr/bin/env python3
"""
RQ Worker 启动脚本
启动方式: python scripts/start_worker.py
依赖: Redis 已启动，.env 配置正确
"""

import os
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

try:
    import redis
    from rq import Worker, Queue, Connection

    redis_conn = redis.Redis(
        host=os.getenv("REDIS_HOST", "127.0.0.1"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_PASSWORD", None),
        db=int(os.getenv("REDIS_DB", "0")),
    )
    redis_conn.ping()
    print(f"✓ Redis 已连接: {os.getenv('REDIS_HOST', '127.0.0.1')}:{os.getenv('REDIS_PORT', '6379')}")
except Exception as e:
    print(f"✗ Redis 连接失败: {e}")
    print("  请确保 Redis 已启动，并检查 .env 配置")
    sys.exit(1)


if __name__ == "__main__":
    queues = ["stock_task", "default"]
    print(f"✓ Worker 启动中，监听队列: {queues}")
    with Connection(redis_conn):
        worker = Worker(queues)
        worker.work()
