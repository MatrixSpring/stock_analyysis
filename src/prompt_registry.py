# -*- coding: utf-8 -*-
"""
===================================
Prompt 版本注册中心 — PromptRegistry
===================================

职责：
1. 固化多套分析 Prompt 模板，按版本管理
2. 支持版本切换、A/B 对比、效果追踪
3. 避免硬编码 Prompt，统一从注册中心获取
4. 模板变量替换（{stock_code}, {market} 等）
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# Prompt 模板
# ============================================================

@dataclass
class PromptTemplate:
    """单个 Prompt 模板"""
    name: str               # 模板名
    version: str
    description: str = ""
    template: str = ""      # 含 {变量} 占位符
    variables: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def render(self, **kwargs) -> str:
        """渲染模板，填充变量"""
        result = self.template
        for var in self.variables:
            value = kwargs.get(var, "")
            result = result.replace(f"{{{var}}}", str(value))

        # 清理未填充的变量
        import re
        result = re.sub(r'\{[^}]+\}', '', result)
        return result.strip()

    def hash(self) -> str:
        return hashlib.md5(self.template.encode()).hexdigest()[:16]


# ============================================================
# 内置模板
# ============================================================

BUILTIN_TEMPLATES: Dict[str, List[PromptTemplate]] = {
    "full_analysis": [
        PromptTemplate(
            name="full_analysis",
            version="v3.0",
            description="五维一体完整分析（含RAG上下文）",
            variables=["stock_code", "stock_name", "market", "technical_summary",
                       "capital_summary", "institutional_summary",
                       "macro_summary", "industry_summary", "rag_context"],
            template="""## 五维一体分析任务

**标的**: {stock_name} ({stock_code}) | **市场**: {market}

### 五维数据

1. **技术面**: {technical_summary}
2. **资金行为**: {capital_summary}
3. **机构观点**: {institutional_summary}
4. **宏观博弈**: {macro_summary}
5. **产业链舆情**: {industry_summary}

### 知识库检索
{rag_context}

### 分析要求
请基于以上五维数据，给出：
1. 综合研判结论（看多/看空/中性）及置信度
2. 各维度关键矛盾点
3. 建议操作方向、仓位和风险提示
4. 所有结论必须引用具体数据来源""",
            tags=["production", "v3"],
        ),
        PromptTemplate(
            name="full_analysis",
            version="v2.0",
            description="基础版分析（无RAG）",
            variables=["stock_code", "stock_name", "technical_summary"],
            template="""分析 {stock_name} ({stock_code}):

技术面数据: {technical_summary}

请给出交易建议。""",
            tags=["legacy", "v2"],
        ),
    ],

    "market_review": [
        PromptTemplate(
            name="market_review",
            version="v1.0",
            description="大盘复盘分析",
            variables=["date", "index_data", "sector_performance",
                       "macro_events", "sentiment"],
            template="""## 大盘复盘: {date}

### 指数表现
{index_data}

### 板块轮动
{sector_performance}

### 宏观事件
{macro_events}

### 市场情绪
{sentiment}

请分析：
1. 当日市场特征
2. 资金流向和板块轮动逻辑
3. 短期（1-5天）市场判断""",
            tags=["production"],
        ),
    ],

    "strategy_review": [
        PromptTemplate(
            name="strategy_review",
            version="v1.0",
            description="策略回测复盘",
            variables=["strategy_name", "period", "metrics", "trades_summary"],
            template="""## 策略复盘: {strategy_name}

回测期间: {period}
绩效指标: {metrics}
交易摘要: {trades_summary}

请分析策略优缺点和改进建议。""",
            tags=["production"],
        ),
    ],

    "sentiment_analysis": [
        PromptTemplate(
            name="sentiment_analysis",
            version="v1.0",
            description="舆情+宏观综合分析",
            variables=["stock_code", "stock_name", "news_sentiment",
                       "industry_boom", "macro_risk"],
            template="""## 舆情+宏观分析: {stock_name} ({stock_code})

舆情: {news_sentiment}
行业景气: {industry_boom}
宏观风险: {macro_risk}

请综合判断外部环境对标的的影响。""",
            tags=["production"],
        ),
    ],
}


# ============================================================
# 注册中心
# ============================================================

class PromptRegistry:
    """
    Prompt 版本注册中心。

    使用方式：
        reg = PromptRegistry()
        reg.load_builtins()

        tmpl = reg.get("full_analysis", version="v3.0")
        prompt = tmpl.render(stock_code="600519", ...)

        # A/B 对比
        results = reg.compare("full_analysis", "v2.0", "v3.0", stock_code="600519")
    """

    def __init__(self):
        self._templates: Dict[str, Dict[str, PromptTemplate]] = {}
        self._active_versions: Dict[str, str] = {}   # name → active version
        self._usage_stats: Dict[str, int] = {}       # version_key → count

    # ============================================================
    # 模板管理
    # ============================================================

    def register(self, template: PromptTemplate):
        """注册模板"""
        name = template.name
        if name not in self._templates:
            self._templates[name] = {}
        self._templates[name][template.version] = template
        logger.info(f"[PromptRegistry] 注册: {name} v{template.version}")

    def load_builtins(self):
        """加载内置模板"""
        for templates in BUILTIN_TEMPLATES.values():
            for tmpl in templates:
                self.register(tmpl)
        # 设默认活跃版本
        for name, versions in self._templates.items():
            sorted_versions = sorted(versions.keys(), reverse=True)
            self._active_versions[name] = sorted_versions[0]
        logger.info(
            f"[PromptRegistry] 加载 {sum(len(v) for v in self._templates.values())} 个内置模板"
        )

    def get(self, name: str, version: Optional[str] = None) -> Optional[PromptTemplate]:
        """获取模板（不指定版本则用活跃版本）"""
        versions = self._templates.get(name, {})
        if not versions:
            return None
        if version:
            return versions.get(version)
        active = self._active_versions.get(name)
        return versions.get(active) if active else list(versions.values())[0]

    def set_active(self, name: str, version: str):
        """设置活跃版本"""
        if name not in self._templates or version not in self._templates[name]:
            raise ValueError(f"模板 {name} v{version} 不存在")
        self._active_versions[name] = version
        logger.info(f"[PromptRegistry] 切换 {name} → v{version}")

    def list_templates(self) -> List[Dict[str, Any]]:
        """列出所有模板"""
        result = []
        for name, versions in self._templates.items():
            for ver, tmpl in versions.items():
                result.append({
                    "name": name,
                    "version": ver,
                    "description": tmpl.description,
                    "active": self._active_versions.get(name) == ver,
                    "tags": tmpl.tags,
                    "hash": tmpl.hash(),
                })
        return result

    def list_versions(self, name: str) -> List[str]:
        return sorted(self._templates.get(name, {}).keys(), reverse=True)

    # ============================================================
    # 渲染
    # ============================================================

    def render(
        self, name: str, version: Optional[str] = None, **variables,
    ) -> Optional[str]:
        """渲染 Prompt（自动引用活跃版本）"""
        tmpl = self.get(name, version)
        if tmpl is None:
            return None
        # 使用统计
        key = f"{name}@{tmpl.version}"
        self._usage_stats[key] = self._usage_stats.get(key, 0) + 1
        return tmpl.render(**variables)

    # ============================================================
    # A/B 对比
    # ============================================================

    def compare(
        self, name: str, version_a: str, version_b: str,
        **variables,
    ) -> Dict[str, Any]:
        """对比两个版本渲染结果"""
        tmpl_a = self.get(name, version_a)
        tmpl_b = self.get(name, version_b)

        return {
            "template": name,
            "version_a": version_a,
            "version_b": version_b,
            "prompt_a": tmpl_a.render(**variables)[:500] if tmpl_a else None,
            "prompt_b": tmpl_b.render(**variables)[:500] if tmpl_b else None,
            "hash_a": tmpl_a.hash() if tmpl_a else "",
            "hash_b": tmpl_b.hash() if tmpl_b else "",
            "diff_chars": (
                abs(len(tmpl_a.template) - len(tmpl_b.template))
                if tmpl_a and tmpl_b else 0
            ),
        }

    # ============================================================
    # 统计
    # ============================================================

    def get_stats(self) -> Dict[str, Any]:
        return {
            "templates": self.list_templates(),
            "active_versions": dict(self._active_versions),
            "usage": dict(self._usage_stats),
        }


# 全局实例
_registry: Optional[PromptRegistry] = None


def get_prompt_registry() -> PromptRegistry:
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
        _registry.load_builtins()
    return _registry
