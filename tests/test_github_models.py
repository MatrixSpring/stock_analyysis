# -*- coding: utf-8 -*-
"""GitHub Models 模块测试"""

import pytest
from unittest.mock import MagicMock, patch
from src.llm.github_models import (
    GitHubModelsProvider, TokenBucket, DEFAULT_FREE_MODELS,
    sync_compare, GitHubModelConfig,
)


class TestTokenBucket:
    def test_acquire_within_limit(self):
        bucket = TokenBucket(rpm=10, tpm=10000)
        for _ in range(10):
            assert bucket.acquire(500) is True

    def test_acquire_exceed_rpm(self):
        bucket = TokenBucket(rpm=5, tpm=10000)
        for _ in range(5):
            bucket.acquire(100)
        assert bucket.acquire(100) is False

    def test_acquire_exceed_tpm(self):
        bucket = TokenBucket(rpm=10, tpm=1000)
        assert bucket.acquire(600) is True
        assert bucket.acquire(500) is False  # 600+500 > 1000

    def test_wait_and_acquire_timeout(self):
        bucket = TokenBucket(rpm=1, tpm=100)
        bucket.acquire(100)  # exhaust
        assert bucket.wait_and_acquire(timeout=0.1) is False


class TestGitHubModelsProvider:
    def setup_method(self):
        self.provider = GitHubModelsProvider(
            api_key="test_key_123",
            model_list=["gpt-4o", "gpt-4o-mini"],
        )

    def test_enabled_with_key(self):
        assert self.provider.enabled is True

    def test_disabled_without_key(self):
        p = GitHubModelsProvider(api_key="")
        assert p.enabled is False

    def test_register_models(self):
        entries = self.provider.register_models()
        assert len(entries) == 2
        assert entries[0]["model_name"] == "github/gpt-4o"
        assert entries[0]["litellm_params"]["input_cost_per_token"] == 0.0

    def test_is_free_model(self):
        assert GitHubModelsProvider.is_free_model("gpt-4o") is True
        assert GitHubModelsProvider.is_free_model("gpt-4o-mini") is True
        assert GitHubModelsProvider.is_free_model("non-free-model") is False

    def test_compare_disabled(self):
        p = GitHubModelsProvider(api_key="")
        import asyncio
        results = asyncio.run(p.compare("test", "prompt"))
        assert results[0]["success"] is False

    @patch('src.llm.github_models.GitHubModelsProvider._call_model')
    def test_compare_with_mock(self, mock_call):
        mock_call.side_effect = [
            {"model": "gpt-4o", "content": "看多", "success": True, "duration_ms": 100},
            {"model": "gpt-4o-mini", "content": "看多", "success": True, "duration_ms": 120},
        ]
        import asyncio
        results = asyncio.run(self.provider.compare("test context", "test prompt"))
        assert len(results) == 2
        assert all(r["success"] for r in results)

    def test_build_consensus_unanimous(self):
        results = [
            {"model": "m1", "content": "趋势看多，风险可控，建议买入", "success": True},
            {"model": "m2", "content": "走势看多，波动正常，继续持仓", "success": True},
        ]
        consensus = self.provider.build_consensus(results)
        assert consensus["status"] == "success"
        assert consensus["reliability_score"] > 0

    def test_build_consensus_divergent(self):
        results = [
            {"model": "m1", "content": "趋势看多，建议买入", "success": True},
            {"model": "m2", "content": "走势看空，建议卖出", "success": True},
        ]
        consensus = self.provider.build_consensus(results)
        assert consensus["reliability_score"] < 80

    def test_build_consensus_all_failed(self):
        results = [
            {"model": "m1", "error": "timeout", "success": False},
            {"model": "m2", "error": "rate limit", "success": False},
        ]
        consensus = self.provider.build_consensus(results)
        assert consensus["status"] == "fail"

    def test_cache_key(self):
        key1 = GitHubModelsProvider.cache_key("600519", "full", ["a", "b"])
        key2 = GitHubModelsProvider.cache_key("600519", "full", ["b", "a"])
        assert key1 == key2  # order-independent

    def test_zero_cost_config(self):
        cfg = GitHubModelsProvider.zero_cost_config()
        assert cfg["input_cost_per_token"] == 0.0
        assert cfg["disable_budget_check"] is True


class TestGitHubModelConfig:
    def test_defaults(self):
        cfg = GitHubModelConfig(
            model_name="gpt-4o",
            api_key="test",
        )
        assert cfg.api_base == "https://models.inference.ai.azure.com"
        assert cfg.timeout == 60
        assert cfg.temperature == 0.3
