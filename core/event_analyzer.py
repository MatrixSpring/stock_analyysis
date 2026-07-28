# -*- coding: utf-8 -*-
"""
===================================
新闻事件解析引擎 — core/event_analyzer.py
===================================

接收用户输入的新闻/公告文本，调用 LLM Gateway 解析为结构化数据，
自动写入 GlobalState 并触发图谱渲染、状态面板刷新。

流程：
1. 用户提交新闻 → gateway 选择对应 LLM → 结构化解析
2. JSON 校验通过 → 创建 EventItem → 写入 GlobalState.event_state (status=pending)
3. 自动生成产业链传导节点和链路
4. 通知前端渲染图谱（灰色草稿态）

使用方式：
    from core.event_analyzer import EventAnalyzer
    analyzer = EventAnalyzer()
    result = analyzer.parse_news("苹果上调iPhone新机订单...")
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.global_state import GlobalState, EventItem, IndustryChainNode, TransferLink
from core.utils import generate_id, validate_event_json
from llm.gateway import get_gateway, LLMResult

logger = logging.getLogger(__name__)


class EventAnalyzer:
    """
    新闻事件解析引擎。

    负责：LLM 调用 → JSON 校验 → 状态写入 → 图谱生成
    """

    def __init__(self):
        self.gateway = get_gateway()
        self.state = GlobalState.get_instance()

    # ---- 主入口 ----

    def parse_news(self, news_text: str) -> Dict[str, Any]:
        """
        解析新闻文本，返回处理结果。

        Returns:
            {"success": bool, "event_id": str, "error": str | None, "parsed": dict | None}
        """
        # 1. 调用 LLM 解析
        llm_result = self.gateway.analyze_news(news_text)
        if not llm_result.success:
            return {"success": False, "event_id": "", "error": llm_result.error}

        parsed = llm_result.data
        if not parsed:
            return {"success": False, "event_id": "", "error": "LLM 返回空数据"}

        # 2. 校验 JSON 结构
        is_valid, errors = validate_event_json(parsed)
        if not is_valid:
            logger.warning(f"[EventAnalyzer] JSON 校验失败: {errors}")
            # 不阻断流程，标注校验问题供人工审核
            parsed["_validation_errors"] = errors

        # 3. 创建事件条目
        event_id = generate_id("evt")
        meta = parsed.get("event_meta", {})

        event = EventItem(
            event_id=event_id,
            title=meta.get("event_title", "未命名事件"),
            source_type=meta.get("source_type", "新闻"),
            direction=meta.get("overall_direction", "neutral"),
            strength=meta.get("impact_strength", 5),
            time_cycle=meta.get("impact_cycle", "middle"),
            audit_status="pending",
            raw_text=news_text,
            parsed_json=parsed,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )

        # 4. 生成产业链传导图谱
        link_ids = self._build_transfer_graph(event_id, parsed.get("transfer_chain", []))
        event.transfer_links = link_ids

        # 5. 写入 GlobalState
        self.state.add_event(event)
        self.state.active_event_id = event_id

        logger.info(
            f"[EventAnalyzer] 事件解析完成: {event.title} "
            f"(方向={event.direction}, 强度={event.strength}, 链路数={len(link_ids)})"
        )

        return {
            "success": True,
            "event_id": event_id,
            "error": None,
            "parsed": parsed,
            "link_count": len(link_ids),
        }

    # ---- 图谱生成 ----

    def _build_transfer_graph(self, event_id: str, transfer_chain: list) -> List[str]:
        """根据传导链路生成图谱节点和连线"""
        link_ids = []
        event_meta = self.state.events[event_id].parsed_json.get("event_meta", {})
        source_name = event_meta.get("event_title", "事件源头")

        # 创建事件源节点
        source_node_id = generate_id("node")
        source_node = IndustryChainNode(
            node_id=source_node_id,
            node_type="event",
            name=source_name,
            level=0,
            properties={"event_id": event_id, "direction": event_meta.get("overall_direction", "neutral")},
        )
        self.state.add_chain_node(source_node)

        for i, link_data in enumerate(transfer_chain):
            from_name = link_data.get("from_node", "")
            to_name = link_data.get("to_node", "")

            # 查找或创建节点
            from_id = self._find_or_create_node(from_name, "upstream")
            to_id = self._find_or_create_node(to_name, "company")

            # 创建传导链路
            link_id = generate_id("link")
            link = TransferLink(
                link_id=link_id,
                from_node=from_id,
                to_node=to_id,
                direction=link_data.get("direction", "neutral"),
                strength=float(link_data.get("strength", 5)),
                logic_text=link_data.get("transfer_logic", ""),
                source_event_id=event_id,
                audit_status="pending",
            )
            self.state.add_transfer_link(link)
            link_ids.append(link_id)

        return link_ids

    def _find_or_create_node(self, name: str, node_type: str) -> str:
        """查找已有节点或创建新节点"""
        for nid, node in self.state.industry_nodes.items():
            if node.name == name:
                return nid

        node_id = generate_id("node")
        node = IndustryChainNode(
            node_id=node_id,
            node_type=node_type,
            name=name,
            level=0,
        )
        self.state.add_chain_node(node)
        return node_id

    # ---- 审核操作 ----

    def confirm_event(self, event_id: str):
        """审核通过事件"""
        self.state.confirm_event(event_id)
        # TODO: 触发传导仿真引擎重新运算，更新股票预期和资金风险参数

    def invalidate_event(self, event_id: str):
        """驳回事件"""
        self.state.invalidate_event(event_id)

    # ---- 状态查询 ----

    def get_event_detail(self, event_id: str) -> Optional[Dict[str, Any]]:
        """获取事件详情（含关联图谱）"""
        event = self.state.events.get(event_id)
        if not event:
            return None

        links = [
            self.state.transfer_links[lid].__dict__
            for lid in event.transfer_links
            if lid in self.state.transfer_links
        ]

        return {
            "event": event.__dict__,
            "transfer_links": links,
            "industry_nodes": {
                nid: node.__dict__
                for nid, node in self.state.industry_nodes.items()
            },
        }
