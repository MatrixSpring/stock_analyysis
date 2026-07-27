# -*- coding: utf-8 -*-
"""
===================================
RAG 向量知识库 — VectorStore
===================================

职责：
1. 文本嵌入（TF-IDF + 余弦相似度，零外部依赖）
2. 向量存储与索引
3. 语义检索 + 关键词混合搜索

入库内容：券商研报、产业新闻、政策文件、地缘事件、历史行情事件
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import threading
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ============================================================
# 轻量级 TF-IDF 引擎
# ============================================================

class TfidfEngine:
    """轻量 TF-IDF 向量化引擎（无需 scikit-learn）"""

    def __init__(self, max_features: int = 2048):
        self._max_features = max_features
        self._vocabulary: Dict[str, int] = {}  # word → index
        self._idf: np.ndarray = np.array([])
        self._fitted = False

    def fit(self, documents: List[str]):
        """构建词表和 IDF"""
        # 词频统计
        doc_count = len(documents)
        df = Counter()
        tokenized_docs = []

        for doc in documents:
            tokens = self._tokenize(doc)
            tokenized_docs.append(tokens)
            df.update(set(tokens))

        # 选 top-N 词
        top_words = [w for w, _ in df.most_common(self._max_features)]
        self._vocabulary = {w: i for i, w in enumerate(top_words)}

        # IDF
        self._idf = np.zeros(len(self._vocabulary))
        for tokens in tokenized_docs:
            for word in set(tokens):
                idx = self._vocabulary.get(word)
                if idx is not None:
                    self._idf[idx] += 1

        self._idf = np.log((doc_count + 1) / (self._idf + 1)) + 1
        self._fitted = True

    def transform(self, documents: List[str]) -> np.ndarray:
        """文档 → TF-IDF 矩阵"""
        if not self._fitted:
            raise RuntimeError("请先调用 fit()")
        matrix = np.zeros((len(documents), len(self._vocabulary)))
        for i, doc in enumerate(documents):
            tokens = self._tokenize(doc)
            tf = Counter(tokens)
            for word, count in tf.items():
                idx = self._vocabulary.get(word)
                if idx is not None:
                    matrix[i, idx] = count * self._idf[idx]
            # L2 归一化
            norm = np.linalg.norm(matrix[i])
            if norm > 0:
                matrix[i] /= norm
        return matrix

    def fit_transform(self, documents: List[str]) -> np.ndarray:
        self.fit(documents)
        return self.transform(documents)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """中文+英文分词（简易版）"""
        # 中文按 2-gram 分词
        cleaned = re.sub(r'[^\w一-鿿]', ' ', text.lower())
        words = []
        # 提取英文单词
        eng_words = re.findall(r'[a-z]+', cleaned)
        words.extend(eng_words)
        # 中文 2-gram
        chinese = re.findall(r'[一-鿿]+', text)
        for segment in chinese:
            for i in range(len(segment) - 1):
                words.append(segment[i:i+2])
            words.append(segment[-1])  # 单字也保留
        return words


# ============================================================
# 文档存储
# ============================================================

@dataclass
class KnowledgeDoc:
    """知识文档"""
    id: str
    title: str
    content: str
    source: str = ""        # 研报/新闻/政策/事件
    category: str = ""       # policy/industry/geopolitics/macro/research
    published_at: str = ""
    url: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class VectorStore:
    """
    向量知识库。

    使用方式：
        store = VectorStore()
        store.add(doc1, doc2, ...)
        results = store.search("芯片制裁影响", top_k=5)
    """

    def __init__(self, persist_dir: Optional[str] = None):
        self._docs: Dict[str, KnowledgeDoc] = {}
        self._tfidf = TfidfEngine(max_features=2048)
        self._vectors: np.ndarray = np.array([])
        self._doc_ids: List[str] = []
        self._persist_dir = Path(persist_dir) if persist_dir else None
        self._lock = threading.Lock()

        if self._persist_dir:
            self._persist_dir.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    # ============================================================
    # 文档管理
    # ============================================================

    def add(self, *docs: KnowledgeDoc):
        """添加文档到知识库"""
        with self._lock:
            for doc in docs:
                if not doc.id:
                    doc.id = hashlib.md5(
                        (doc.title + doc.content[:200]).encode()
                    ).hexdigest()[:12]
                self._docs[doc.id] = doc

    def add_text(
        self, title: str, content: str, source: str = "",
        category: str = "", **meta,
    ) -> str:
        """快速添加文本"""
        doc = KnowledgeDoc(
            id="",
            title=title,
            content=content,
            source=source,
            category=category,
            metadata=meta,
        )
        self.add(doc)
        return doc.id

    def remove(self, doc_id: str):
        with self._lock:
            self._docs.pop(doc_id, None)

    def count(self) -> int:
        return len(self._docs)

    # ============================================================
    # 索引构建
    # ============================================================

    def build_index(self):
        """（重新）构建 TF-IDF 索引"""
        with self._lock:
            if not self._docs:
                logger.warning("[VectorStore] 无文档，跳过索引构建")
                return

            self._doc_ids = list(self._docs.keys())
            texts = [
                f"{self._docs[did].title} {self._docs[did].content}"
                for did in self._doc_ids
            ]
            self._vectors = self._tfidf.fit_transform(texts)
            logger.info(
                f"[VectorStore] 索引构建完成: {len(self._doc_ids)} docs, "
                f"{len(self._tfidf._vocabulary)} features"
            )

    # ============================================================
    # 检索
    # ============================================================

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.05,
        category_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        语义检索。

        Returns:
            [{doc_id, title, content, source, category, score, snippet}]
        """
        if len(self._vectors) == 0:
            return []

        query_vec = self._tfidf.transform([query])[0]

        # 余弦相似度
        scores = np.dot(self._vectors, query_vec)
        top_indices = np.argsort(-scores)[:top_k * 2]

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score < min_score:
                continue
            doc_id = self._doc_ids[idx]
            doc = self._docs.get(doc_id)
            if doc is None:
                continue
            if category_filter and doc.category != category_filter:
                continue
            results.append({
                "doc_id": doc.id,
                "title": doc.title,
                "content": doc.content[:300],
                "source": doc.source,
                "category": doc.category,
                "score": round(score, 4),
                "snippet": self._extract_snippet(doc.content, query),
                "published_at": doc.published_at,
                "url": doc.url,
                "tags": doc.tags,
            })

        return results[:top_k]

    def search_for_analysis(
        self,
        stock_code: str,
        stock_name: str = "",
        industry: str = "",
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        个股分析专用检索：按维度分别检索。

        Returns:
            {category: [results]}
        """
        queries = {
            "industry": f"{stock_name} {industry} 产业链 供需 产能 景气 订单",
            "policy": f"{stock_name} {industry} 政策 监管 审批 补贴 扶持",
            "geopolitics": "地缘 关税 制裁 出口管制 贸易 冲突",
            "research": f"{stock_name} 研报 评级 目标价 盈利预测 调研",
        }

        result = {}
        for category, query in queries.items():
            result[category] = self.search(
                query, top_k=3, category_filter=category,
            )
        return result

    def get_context_for_llm(
        self,
        stock_code: str,
        stock_name: str = "",
        max_chars: int = 2000,
    ) -> str:
        """生成 LLM 可用的检索上下文"""
        all_results = self.search_for_analysis(stock_code, stock_name)

        lines = ["## 知识库检索上下文", ""]
        char_count = 0

        for category, results in all_results.items():
            if not results:
                continue
            lines.append(f"### {category}")
            for r in results[:2]:
                snippet = r["snippet"][:400]
                lines.append(f"- [{r['source']}] {r['title']}: {snippet}")
                char_count += len(snippet)
                if char_count > max_chars:
                    break
            lines.append("")

        return "\n".join(lines) if len(lines) > 2 else ""

    # ============================================================
    # 持久化
    # ============================================================

    def save_to_disk(self):
        if self._persist_dir is None:
            return
        data = {
            "docs": [
                {
                    "id": d.id, "title": d.title, "content": d.content,
                    "source": d.source, "category": d.category,
                    "published_at": d.published_at, "url": d.url,
                    "tags": d.tags, "metadata": d.metadata,
                }
                for d in self._docs.values()
            ]
        }
        path = self._persist_dir / "knowledge_base.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"[VectorStore] 持久化: {len(self._docs)} docs → {path}")

    # ============================================================
    # 内部
    # ============================================================

    def _extract_snippet(self, text: str, query: str, window: int = 80) -> str:
        """提取查询相关的文本片段"""
        query_words = set(TfidfEngine._tokenize(query))
        best_pos = 0
        best_score = 0
        for i in range(len(text) - window):
            chunk = text[i:i + window]
            score = sum(1 for w in query_words if w in chunk)
            if score > best_score:
                best_score = score
                best_pos = i
        start = max(0, best_pos - 20)
        return text[start:start + window + 40] + ("..." if start + window + 40 < len(text) else "")

    def _load_from_disk(self):
        if self._persist_dir is None:
            return
        path = self._persist_dir / "knowledge_base.json"
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for raw in data.get("docs", []):
                doc = KnowledgeDoc(
                    id=raw.get("id", ""),
                    title=raw.get("title", ""),
                    content=raw.get("content", ""),
                    source=raw.get("source", ""),
                    category=raw.get("category", ""),
                    published_at=raw.get("published_at", ""),
                    url=raw.get("url", ""),
                    tags=raw.get("tags", []),
                    metadata=raw.get("metadata", {}),
                )
                self._docs[doc.id] = doc
            logger.info(f"[VectorStore] 从磁盘恢复: {len(self._docs)} docs")
        except Exception as e:
            logger.warning(f"[VectorStore] 磁盘加载失败: {e}")


# 全局实例
_store_instance: Optional[VectorStore] = None
_store_lock = threading.Lock()


def get_vector_store(persist_dir: Optional[str] = None) -> VectorStore:
    global _store_instance
    if _store_instance is None:
        with _store_lock:
            if _store_instance is None:
                _store_instance = VectorStore(persist_dir=persist_dir)
    return _store_instance
