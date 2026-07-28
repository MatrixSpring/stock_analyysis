# -*- coding: utf-8 -*-
"""
===================================
全局统一状态中心 — GlobalState
===================================

所有 UI 组件、业务引擎的统一数据源。
规则：任何业务参数唯一数据源 = GlobalState，禁止代码直接读写 st.session_state["xxx"]。

五大顶层状态分组：
- stock_state:     股票技术位置、支撑压力、趋势、15日周期情景
- capital_state:   资金博弈、融资压力、北向、筹码
- industry_chain_state: 产业链节点、传导链路
- expect_state:    市场预期、景气度、分歧
- event_state:     新闻事件列表、审核状态

使用方式：
    from core.global_state import GlobalState
    gs = GlobalState.get_instance()
    gs.update_stock_state({"code": "600519", "support": 1800.0})
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from threading import Lock

logger = logging.getLogger(__name__)


# ============================================================
# 状态数据类定义
# ============================================================

@dataclass
class StockInfo:
    """单只股票的完整状态快照"""
    code: str = ""
    name: str = ""
    support_price: float = 0.0          # 支撑位
    resistance_price: float = 0.0       # 压力位
    trend: str = "neutral"              # up / down / neutral
    volatility: float = 0.0             # 波动率
    # 15日周期情景
    optimistic_target: float = 0.0
    base_target: float = 0.0
    pessimistic_target: float = 0.0
    trigger_points: List[float] = field(default_factory=list)
    last_update: str = ""


@dataclass
class CapitalState:
    """资金博弈 & 资金压力状态"""
    margin_risk_level: str = "low"      # low / mid / high
    north_bound_sentiment: str = "neutral"
    chip_concentration: str = "normal"
    sector_flow: str = "flat"           # inflow / outflow / flat
    liquidation_pressure: float = 0.0   # 0~1
    long_short_ratio: float = 1.0
    last_update: str = ""


@dataclass
class IndustryChainNode:
    """产业链节点"""
    node_id: str = ""
    node_type: str = "company"          # event / company / upstream / downstream
    name: str = ""
    level: int = 0                      # 产业链层级
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransferLink:
    """传导链路"""
    link_id: str = ""
    from_node: str = ""
    to_node: str = ""
    direction: str = "positive"          # positive / negative
    strength: float = 5.0               # 1~10
    decay_factor: float = 0.8           # 传导衰减系数
    logic_text: str = ""
    time_cycle: str = "middle"          # short / middle / long
    source_event_id: str = ""           # 来源事件
    audit_status: str = "pending"       # pending / confirmed / invalid


@dataclass
class ExpectState:
    """市场预期状态"""
    prosperity_stage: str = "stable"    # improve / worsen / stable
    estimate_revision: str = "stable"   # upward / downward / stable
    divergence_level: str = "mid"       # high / mid / low
    valuation_narrative: str = ""
    last_update: str = ""


@dataclass
class EventItem:
    """新闻事件条目"""
    event_id: str = ""
    title: str = ""
    source_type: str = ""               # 新闻/政策/公司公告/行业纪要/传闻
    direction: str = "neutral"          # positive / negative / neutral
    strength: int = 5                   # 1~10
    time_cycle: str = "middle"          # short / middle / long
    audit_status: str = "pending"       # pending / confirmed / invalid
    raw_text: str = ""
    parsed_json: Dict[str, Any] = field(default_factory=dict)
    transfer_links: List[str] = field(default_factory=list)  # link_ids
    created_at: str = ""
    updated_at: str = ""


# ============================================================
# 变更钩子类型
# ============================================================

StateChangeCallback = Callable[[str, Any], None]
"""回调签名: callback(state_group: str, data: Any) -> None"""


# ============================================================
# GlobalState 单例
# ============================================================

class GlobalState:
    """
    全局统一状态中心（线程安全单例）。

    五大状态分组 + 变更订阅机制。
    所有模块通过 get_instance() 获取同一实例，保证数据一致性。
    """

    _instance: Optional["GlobalState"] = None
    _lock: Lock = Lock()

    def __init__(self):
        # 股票状态: code -> StockInfo
        self.stock_state: Dict[str, StockInfo] = {}

        # 资金状态
        self.capital_state: CapitalState = CapitalState()

        # 产业链状态
        self.industry_nodes: Dict[str, IndustryChainNode] = {}
        self.transfer_links: Dict[str, TransferLink] = {}
        self.focus_stock_code: str = ""

        # 预期状态
        self.expect_state: ExpectState = ExpectState()

        # 事件状态
        self.events: Dict[str, EventItem] = {}
        self.active_event_id: Optional[str] = None

        # 变更订阅者
        self._subscribers: Dict[str, List[StateChangeCallback]] = {
            "stock": [],
            "capital": [],
            "industry_chain": [],
            "expect": [],
            "event": [],
        }

        # 更新锁：防止循环刷新死循环
        self._updating: bool = False
        self._pending_updates: Dict[str, Any] = {}

    # ---- 单例 ----

    @classmethod
    def get_instance(cls) -> "GlobalState":
        """获取全局唯一实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    logger.info("[GlobalState] 全局状态中心初始化完成")
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """重置实例（仅测试用）"""
        with cls._lock:
            cls._instance = None

    # ---- 变更订阅 ----

    def subscribe(self, group: str, callback: StateChangeCallback):
        """订阅某状态组的变更通知"""
        if group in self._subscribers:
            self._subscribers[group].append(callback)

    def unsubscribe(self, group: str, callback: StateChangeCallback):
        """取消订阅"""
        if group in self._subscribers:
            self._subscribers[group] = [
                cb for cb in self._subscribers[group] if cb is not callback
            ]

    def _notify(self, group: str, data: Any):
        """通知所有订阅者"""
        for cb in self._subscribers.get(group, []):
            try:
                cb(group, data)
            except Exception as e:
                logger.warning(f"[GlobalState] 通知订阅者失败 {group}: {e}")

    # ---- 股票状态 ----

    def get_stock(self, code: str) -> StockInfo:
        """获取单只股票状态，不存在则创建空对象"""
        if code not in self.stock_state:
            self.stock_state[code] = StockInfo(code=code)
        return self.stock_state[code]

    def update_stock_state(self, code: str, **kwargs):
        """更新单只股票状态"""
        stock = self.get_stock(code)
        for key, value in kwargs.items():
            if hasattr(stock, key):
                setattr(stock, key, value)
        stock.last_update = datetime.now().isoformat()
        self._notify("stock", {"code": code, "changes": kwargs})

    def get_all_stocks(self) -> Dict[str, StockInfo]:
        return dict(self.stock_state)

    # ---- 资金状态 ----

    def update_capital_state(self, **kwargs):
        """更新资金状态"""
        for key, value in kwargs.items():
            if hasattr(self.capital_state, key):
                setattr(self.capital_state, key, value)
        self.capital_state.last_update = datetime.now().isoformat()
        self._notify("capital", kwargs)

    # ---- 产业链状态 ----

    def add_chain_node(self, node: IndustryChainNode):
        """新增产业链节点"""
        self.industry_nodes[node.node_id] = node
        self._notify("industry_chain", {"action": "add_node", "node": node})

    def remove_chain_node(self, node_id: str):
        """删除产业链节点"""
        if node_id in self.industry_nodes:
            del self.industry_nodes[node_id]
            # 同时删除关联的传导链路
            to_remove = [
                lid for lid, link in self.transfer_links.items()
                if link.from_node == node_id or link.to_node == node_id
            ]
            for lid in to_remove:
                del self.transfer_links[lid]
            self._notify("industry_chain", {"action": "remove_node", "node_id": node_id})

    def add_transfer_link(self, link: TransferLink):
        """新增传导链路"""
        self.transfer_links[link.link_id] = link
        self._notify("industry_chain", {"action": "add_link", "link": link})

    def update_transfer_link(self, link_id: str, **kwargs):
        """修改传导链路属性"""
        if link_id in self.transfer_links:
            link = self.transfer_links[link_id]
            for key, value in kwargs.items():
                if hasattr(link, key):
                    setattr(link, key, value)
            self._notify("industry_chain", {"action": "update_link", "link_id": link_id, "changes": kwargs})

    def remove_transfer_link(self, link_id: str):
        """删除传导链路"""
        if link_id in self.transfer_links:
            del self.transfer_links[link_id]
            self._notify("industry_chain", {"action": "remove_link", "link_id": link_id})

    # ---- 预期状态 ----

    def update_expect_state(self, **kwargs):
        """更新预期状态"""
        for key, value in kwargs.items():
            if hasattr(self.expect_state, key):
                setattr(self.expect_state, key, value)
        self.expect_state.last_update = datetime.now().isoformat()
        self._notify("expect", kwargs)

    # ---- 事件状态 ----

    def add_event(self, event: EventItem):
        """新增事件（默认待审核）"""
        event.updated_at = datetime.now().isoformat()
        self.events[event.event_id] = event
        self._notify("event", {"action": "add", "event": event})

    def update_event(self, event_id: str, **kwargs):
        """更新事件属性"""
        if event_id in self.events:
            event = self.events[event_id]
            for key, value in kwargs.items():
                if hasattr(event, key):
                    setattr(event, key, value)
            event.updated_at = datetime.now().isoformat()
            self._notify("event", {"action": "update", "event_id": event_id, "changes": kwargs})

    def confirm_event(self, event_id: str):
        """审核通过事件 → 状态变更为 confirmed"""
        self.update_event(event_id, audit_status="confirmed")
        logger.info(f"[GlobalState] 事件 {event_id} 审核通过，纳入预测模型")

    def invalidate_event(self, event_id: str):
        """驳回事件 → 状态变更为 invalid"""
        self.update_event(event_id, audit_status="invalid")
        logger.info(f"[GlobalState] 事件 {event_id} 已废弃")

    def get_pending_events(self) -> List[EventItem]:
        """获取所有待审核事件"""
        return [e for e in self.events.values() if e.audit_status == "pending"]

    def get_confirmed_events(self) -> List[EventItem]:
        """获取所有已生效事件"""
        return [e for e in self.events.values() if e.audit_status == "confirmed"]

    # ---- 全量导出 / 导入 ----

    def get_all_state(self) -> Dict[str, Any]:
        """导出完整状态快照（用于持久化 & 前端同步）"""
        return {
            "stock_state": {k: v.__dict__ for k, v in self.stock_state.items()},
            "capital_state": self.capital_state.__dict__,
            "industry_chain": {
                "nodes": {k: v.__dict__ for k, v in self.industry_nodes.items()},
                "links": {k: v.__dict__ for k, v in self.transfer_links.items()},
            },
            "expect_state": self.expect_state.__dict__,
            "event_state": {
                "events": {k: v.__dict__ for k, v in self.events.items()},
                "active_event_id": self.active_event_id,
            },
            "focus_stock_code": self.focus_stock_code,
        }

    def restore_state(self, snapshot: Dict[str, Any]):
        """从快照恢复状态"""
        # 恢复股票状态
        for code, data in snapshot.get("stock_state", {}).items():
            self.stock_state[code] = StockInfo(**data)

        # 恢复资金状态
        cap = snapshot.get("capital_state", {})
        if cap:
            self.capital_state = CapitalState(**cap)

        # 恢复产业链
        chain = snapshot.get("industry_chain", {})
        for nid, ndata in chain.get("nodes", {}).items():
            self.industry_nodes[nid] = IndustryChainNode(**ndata)
        for lid, ldata in chain.get("links", {}).items():
            self.transfer_links[lid] = TransferLink(**ldata)

        # 恢复预期
        exp = snapshot.get("expect_state", {})
        if exp:
            self.expect_state = ExpectState(**exp)

        # 恢复事件
        ev = snapshot.get("event_state", {})
        for eid, edata in ev.get("events", {}).items():
            self.events[eid] = EventItem(**edata)
        self.active_event_id = ev.get("active_event_id")

        self.focus_stock_code = snapshot.get("focus_stock_code", "")
        logger.info("[GlobalState] 状态快照恢复完成")

    # ---- 防循环锁 ----

    def begin_batch_update(self):
        """开始批量更新（禁用通知，最后统一刷新）"""
        self._updating = True
        self._pending_updates = {}

    def end_batch_update(self):
        """结束批量更新（统一发送通知）"""
        self._updating = False
        for group, data in self._pending_updates.items():
            self._notify(group, data)
        self._pending_updates.clear()
