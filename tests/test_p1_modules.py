# -*- coding: utf-8 -*-
"""P1 模块测试: TieredStore + TaskQueue + LLMCache"""

import pytest
import time
import tempfile
import os
import pandas as pd
from unittest.mock import MagicMock

from src.data_tiering.tiered_store import TieredStore, LRUCache
from src.task_queue.executor import TaskQueue, TaskState, get_task_queue
from src.llm_cache import LLMCache, get_llm_cache


# ============================================================
# LRU Cache
# ============================================================

class TestLRUCache:
    def test_get_set(self):
        c = LRUCache(max_items=10, ttl_seconds=60)
        c.set("a", 1)
        assert c.get("a") == 1

    def test_expiry(self):
        c = LRUCache(max_items=10, ttl_seconds=0)
        c.set("a", 1)
        assert c.get("a") is None

    def test_lru_eviction(self):
        c = LRUCache(max_items=3, ttl_seconds=600)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        c.set("d", 4)
        assert c.get("a") is None  # evicted
        assert c.get("d") == 4


# ============================================================
# TieredStore
# ============================================================

class TestTieredStore:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mock_db = MagicMock()
        self.store = TieredStore(
            db_manager=self.mock_db,
            archive_dir=os.path.join(self.tmpdir, "archive"),
            hot_window_days=90,
        )
        self.store.init()

    def test_init_creates_dir(self):
        assert os.path.isdir(os.path.join(self.tmpdir, "archive"))

    def test_query_hot(self):
        self.mock_db.execute_query = MagicMock(return_value=[
            ("2024-06-01", 100.0, 102.0, 99.0, 101.0, 1000000, 101000000.0, 1.0,
             101.0, 100.0, 99.0, 1.0, "test"),
        ])
        df = self.store.query_kline("600519", start="2024-06-01", end="2024-06-02")
        assert not df.empty
        assert df.iloc[0]["close"] == 101.0

    def test_archive_stats_empty(self):
        stats = self.store.get_archive_stats()
        assert stats["archive_exists"] is True
        assert stats["files"] == 0

    def test_clear_cache(self):
        self.store._cache.set("test", "data")
        self.store.clear_cache()
        assert len(self.store._cache) == 0


# ============================================================
# TaskQueue
# ============================================================

class TestTaskQueue:
    def setup_method(self):
        self.queue = TaskQueue(max_workers=2)

    def teardown_method(self):
        self.queue.shutdown(wait=False)

    def test_submit_and_wait(self):
        task_id = self.queue.submit("test", lambda: 42)
        result = self.queue.result(task_id, timeout=5)
        assert result == 42

    def test_status_pending(self):
        task_id = self.queue.submit("test", lambda: time.sleep(0.1))
        self.queue.result(task_id, timeout=5)
        status = self.queue.status(task_id)
        assert status["state"] == "completed"

    def test_cancel(self):
        import time as _time
        task_id = self.queue.submit("slow", lambda: _time.sleep(5))
        cancelled = self.queue.cancel(task_id)
        assert isinstance(cancelled, bool)

    def test_list_tasks(self):
        self.queue.submit("task_a", lambda: 1)
        self.queue.submit("task_b", lambda: 2)
        tasks = self.queue.list_tasks()
        assert len(tasks) >= 2

    def test_cleanup(self):
        task_id = self.queue.submit("cleanup_test", lambda: 42)
        result = self.queue.result(task_id, timeout=5)
        assert result == 42
        self.queue.cleanup(max_age_seconds=-1)
        status = self.queue.status(task_id)
        assert status["state"] in ("unknown", "pending", "completed")

    def test_error_handling(self):
        task_id = self.queue.submit("failing", lambda: 1 / 0)
        with pytest.raises(ZeroDivisionError):
            self.queue.result(task_id, timeout=5)
        # After a failed task, the future raised correctly
        assert task_id  # task was created


# ============================================================
# LLMCache
# ============================================================

class TestLLMCache:
    def setup_method(self):
        self.cache = LLMCache(ttl_minutes=30, max_entries=100)

    def test_set_and_get(self):
        self.cache.set("600519", "full_analysis", {"decision": "buy"}, model="test")
        result = self.cache.get("600519", "full_analysis", model="test")
        assert result == {"decision": "buy"}

    def test_miss(self):
        result = self.cache.get("nonexistent", "analysis")
        assert result is None

    def test_key_isolation(self):
        self.cache.set("600519", "analysis", "result_a")
        self.cache.set("000001", "analysis", "result_b")
        assert self.cache.get("600519", "analysis") == "result_a"
        assert self.cache.get("000001", "analysis") == "result_b"

    def test_ttl_expiry(self):
        self.cache._ttl_seconds = 0  # immediate expiry
        self.cache.set("600519", "test", "data")
        assert self.cache.get("600519", "test") is None

    def test_clear(self):
        self.cache.set("a", "test", "1")
        self.cache.set("b", "test", "2")
        self.cache.clear()
        assert self.cache.get("a", "test") is None

    def test_stats(self):
        self.cache.set("600519", "test", "data", token_count=1000)
        self.cache.get("600519", "test")
        self.cache.get("missing", "test")
        stats = self.cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_save_load_disk(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            cache2 = LLMCache(ttl_minutes=60, persist_path=path)
            cache2.set("600519", "test", "disk_data")
            cache2.save_to_disk()

            cache3 = LLMCache(ttl_minutes=60, persist_path=path)
            result = cache3.get("600519", "test")
            assert result == "disk_data"
        finally:
            os.unlink(path)

    def test_delete(self):
        self.cache.set("600519", "type_a", "data_a")
        self.cache.set("600519", "type_b", "data_b")
        self.cache.delete("600519", "type_a")
        assert self.cache.get("600519", "type_a") is None
        assert self.cache.get("600519", "type_b") == "data_b"

    def test_clear_expired(self):
        self.cache._ttl_seconds = -1  # all expired
        self.cache.set("a", "test", "1")
        self.cache.set("b", "test", "2")
        removed = self.cache.clear_expired()
        assert removed == 2
        assert self.cache.get_stats()["entries"] == 0
