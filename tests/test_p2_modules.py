# -*- coding: utf-8 -*-
"""P2 模块测试: RAG知识库 + 推理溯源 + Prompt版本管理"""

import pytest
import tempfile, os
from src.rag_knowledge.vector_store import (
    VectorStore, TfidfEngine, KnowledgeDoc
)
from src.analysis_trace import AnalysisTracer, Evidence, TraceRecord
from src.prompt_registry import (
    PromptRegistry, PromptTemplate, get_prompt_registry,
    BUILTIN_TEMPLATES,
)


# ============================================================
# TfidfEngine
# ============================================================

class TestTfidfEngine:
    def test_fit_transform(self):
        engine = TfidfEngine(max_features=256)
        docs = ["芯片制裁 半导体 产业链", "碳中和 新能源 光伏", "美联储 加息 通胀"]
        vecs = engine.fit_transform(docs)
        assert vecs.shape == (3, len(engine._vocabulary))
        assert engine._fitted is True

    def test_cosine_similarity(self):
        engine = TfidfEngine(max_features=128)
        docs = ["芯片 半导体 制裁", "新能源 光伏 储能", "芯片 半导体 出口管制"]
        vecs = engine.fit_transform(docs)
        # 第1篇和第3篇相似（都含芯片/半导体）
        sim_0_2 = float(vecs[0].dot(vecs[2]))
        sim_0_1 = float(vecs[0].dot(vecs[1]))
        assert sim_0_2 > sim_0_1  # 0和2更相似

    def test_transform_before_fit(self):
        engine = TfidfEngine()
        with pytest.raises(RuntimeError):
            engine.transform(["test"])


# ============================================================
# VectorStore
# ============================================================

class TestVectorStore:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = VectorStore(persist_dir=self.tmpdir)

    def test_add_and_search(self):
        self.store.add_text("芯片制裁", "美国宣布对华芯片出口新限制", category="geopolitics")
        self.store.add_text("新能源补贴", "国务院发布新能源汽车购置补贴延续", category="policy")
        self.store.add_text("光伏产能", "光伏产业链产能过剩 硅料价格下跌", category="industry")
        self.store.build_index()

        results = self.store.search("芯片 半导体制裁", top_k=2)
        assert len(results) >= 1
        assert "芯片" in results[0]["title"]

    def test_category_filter(self):
        self.store.add_text("A", "政策内容 AAA", category="policy")
        self.store.add_text("B", "行业内容 BBB", category="industry")
        self.store.build_index()

        results = self.store.search("政策", category_filter="policy", top_k=5)
        assert all(r["category"] == "policy" for r in results)

    def test_empty_search(self):
        self.store.build_index()
        results = self.store.search("test", top_k=5)
        assert results == []

    def test_get_context_for_llm(self):
        self.store.add_text("茅台研报", "贵州茅台目标价2000元 买入评级", category="research")
        self.store.build_index()
        ctx = self.store.get_context_for_llm("600519", "贵州茅台")
        assert isinstance(ctx, str)

    def test_persist_and_load(self):
        self.store.add_text("测试", "测试内容", category="policy")
        self.store.save_to_disk()

        store2 = VectorStore(persist_dir=self.tmpdir)
        assert store2.count() == 1

    def test_search_for_analysis(self):
        self.store.add_text("茅台研报", "买入评级", category="research")
        self.store.add_text("白酒政策", "消费刺激", category="policy")
        self.store.build_index()
        result = self.store.search_for_analysis("600519", "贵州茅台")
        assert "research" in result
        assert "policy" in result


# ============================================================
# AnalysisTracer
# ============================================================

class TestAnalysisTracer:
    def setup_method(self):
        self.tracer = AnalysisTracer()

    def test_create_and_finalize(self):
        trace = self.tracer.create_trace("600519", "full_analysis", model="deepseek")
        self.tracer.add_evidence(trace, "indicator", "MA金叉", "MA5上穿MA20", "kline")
        self.tracer.add_conclusion(trace, "买入", confidence=0.72, reason="技术面偏多")
        self.tracer.finalize(trace, prompt="分析600519...")

        assert trace.stock_code == "600519"
        assert len(trace.evidence) == 1
        assert len(trace.conclusions) == 1
        assert trace.prompt_hash != ""

    def test_export_text(self):
        trace = self.tracer.create_trace("600519")
        self.tracer.add_evidence(trace, "capital", "北向流入", "+5亿", "north_bound")
        self.tracer.add_conclusion(trace, "持有", confidence=0.6)
        text = self.tracer.export_trace_text(trace)
        assert "北向流入" in text
        assert "600519" in text

    def test_search_by_code(self):
        self.tracer.create_trace("600519")
        self.tracer.create_trace("000001")
        results = self.tracer.search(stock_code="600519")
        assert len(results) == 1

    def test_list_all(self):
        self.tracer.create_trace("600519")
        self.tracer.create_trace("000001")
        assert self.tracer.count() == 2
        assert len(self.tracer.list_all()) == 2


# ============================================================
# PromptRegistry
# ============================================================

class TestPromptRegistry:
    def setup_method(self):
        self.reg = PromptRegistry()
        self.reg.load_builtins()

    def test_get_builtin(self):
        tmpl = self.reg.get("full_analysis")
        assert tmpl is not None
        assert tmpl.version == "v3.0"

    def test_render(self):
        prompt = self.reg.render(
            "full_analysis",
            stock_code="600519", stock_name="茅台", market="A",
            technical_summary="多头排列",
            capital_summary="资金流入",
            institutional_summary="机构看多",
            macro_summary="政策友好",
            industry_summary="景气上行",
            rag_context="无",
        )
        assert prompt is not None
        assert "600519" in prompt
        assert "茅台" in prompt
        assert "五维一体" in prompt

    def test_set_active_version(self):
        self.reg.set_active("full_analysis", "v2.0")
        tmpl = self.reg.get("full_analysis")
        assert tmpl.version == "v2.0"

    def test_list_templates(self):
        templates = self.reg.list_templates()
        assert len(templates) >= 4  # at least the builtin ones

    def test_compare_versions(self):
        result = self.reg.compare(
            "full_analysis", "v2.0", "v3.0",
            stock_code="600519",
        )
        assert result["version_a"] == "v2.0"
        assert result["version_b"] == "v3.0"
        assert result["prompt_a"] != result["prompt_b"]

    def test_get_nonexistent(self):
        assert self.reg.get("nonexistent") is None
        assert self.reg.render("nonexistent") is None

    def test_custom_template(self):
        tmpl = PromptTemplate(
            name="custom_test", version="v1.0",
            template="分析 {code}，风格: {style}",
            variables=["code", "style"],
        )
        self.reg.register(tmpl)
        result = self.reg.render("custom_test", code="600519", style="短线")
        assert "600519" in result
        assert "短线" in result
