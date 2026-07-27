# -*- coding: utf-8 -*-
"""
===================================
RAG 向量知识库
===================================

- VectorStore: TF-IDF 向量存储 + 语义检索
- TfidfEngine: 轻量 TF-IDF 引擎（零外部依赖）
- KnowledgeDoc: 知识文档结构

使用方式:
    from src.rag_knowledge import VectorStore, get_vector_store

    store = get_vector_store("./data/knowledge")
    store.add_text("芯片制裁", "美国宣布...", source="新闻", category="geopolitics")
    store.build_index()
    results = store.search("芯片政策影响", top_k=5)
"""

from src.rag_knowledge.vector_store import (
    VectorStore,
    TfidfEngine,
    KnowledgeDoc,
    get_vector_store,
)

__all__ = [
    "VectorStore",
    "TfidfEngine",
    "KnowledgeDoc",
    "get_vector_store",
]
