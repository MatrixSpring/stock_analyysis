# -*- coding: utf-8 -*-
"""
===================================
iframe ↔ Python 双向消息总线 — MessageBus
===================================

解决当前 iframe postMessage 通信不可靠、无规范、无 ACK 的顽疾。

消息协议（JSON 固定格式）：
{
    "msg_id": "uuid",
    "sender": "iframe | backend",
    "action": "update_link | add_node | parse_news | audit_confirm | ...",
    "payload": {},
    "timestamp": 0
}

特性：
- 每条消息携带唯一 msg_id
- 后端处理完成后发送 ACK 回执
- JS 侧提供 sendMessage / onMessage 封装
- 支持请求-响应模式和事件广播模式

使用方式：
    from core.message_bus import MessageBus
    bus = MessageBus()
    bus.register_handler("parse_news", handle_parse_news)
"""

from __future__ import annotations

import json
import logging
import uuid
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

MessageHandler = Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]
"""消息处理器签名: handler(payload) -> response_payload | None"""

# JS 端通信代码模板（嵌入 iframe HTML 使用）
JS_MESSAGE_BUS_TEMPLATE = r"""
// ============================================================
// MessageBus — JavaScript 端通信封装
// 配合 Python core/message_bus.py 使用
// ============================================================

const MessageBus = {
    _handlers: {},
    _pendingRequests: {},

    // 生成唯一消息 ID
    _msgId() {
        return 'msg_' + Date.now() + '_' + Math.random().toString(36).slice(2, 9);
    },

    // 向后端发送消息（不等待响应）
    send(action, payload = {}) {
        const msg = {
            msg_id: this._msgId(),
            sender: 'iframe',
            action: action,
            payload: payload,
            timestamp: Date.now()
        };
        window.parent.postMessage(msg, '*');
        return msg.msg_id;
    },

    // 向后端发送请求并等待 ACK 响应（返回 Promise）
    request(action, payload = {}, timeoutMs = 30000) {
        return new Promise((resolve, reject) => {
            const msgId = this._msgId();
            const msg = {
                msg_id: msgId,
                sender: 'iframe',
                action: action,
                payload: payload,
                timestamp: Date.now()
            };
            this._pendingRequests[msgId] = { resolve, reject };
            window.parent.postMessage(msg, '*');

            // 超时处理
            setTimeout(() => {
                if (this._pendingRequests[msgId]) {
                    delete this._pendingRequests[msgId];
                    reject(new Error(`Request ${action} timed out after ${timeoutMs}ms`));
                }
            }, timeoutMs);
        });
    },

    // 注册消息处理器
    on(action, handler) {
        if (!this._handlers[action]) {
            this._handlers[action] = [];
        }
        this._handlers[action].push(handler);
    },

    // 取消注册
    off(action, handler) {
        if (this._handlers[action]) {
            this._handlers[action] = this._handlers[action].filter(h => h !== handler);
        }
    },

    // 处理收到的消息（在 window message listener 中调用）
    _handleMessage(msg) {
        // 如果是 ACK 回执，resolve pending request
        if (msg.action === '_ack' && msg.payload && msg.payload.reply_to) {
            const pending = this._pendingRequests[msg.payload.reply_to];
            if (pending) {
                delete this._pendingRequests[msg.payload.reply_to];
                if (msg.payload.error) {
                    pending.reject(new Error(msg.payload.error));
                } else {
                    pending.resolve(msg.payload.data);
                }
            }
            return;
        }

        // 分发给注册的处理器
        const handlers = this._handlers[msg.action] || [];
        handlers.forEach(handler => {
            try {
                handler(msg.payload, msg);
            } catch (e) {
                console.error(`[MessageBus] Handler error for ${msg.action}:`, e);
            }
        });
    }
};

// 监听来自后端的消息
window.addEventListener('message', (event) => {
    // 安全校验：只处理来自同源的消息
    // 开发环境允许 '*', 生产环境应校验 event.origin
    if (event.data && event.data.action && event.data.msg_id) {
        MessageBus._handleMessage(event.data);
    }
});
"""


class MessageBus:
    """
    双向消息总线。

    使用方式：
        bus = MessageBus()

        # 注册处理器
        @bus.on("parse_news")
        def handle_parse_news(payload):
            # 处理新闻解析
            return {"status": "ok", "event_id": "evt_001"}

        # 从 Streamlit 前端接收消息
        msg = bus.receive_from_js(json_string)

        # 发送消息到前端
        bus.send_to_js("state_update", global_state_snapshot)
    """

    def __init__(self):
        self._handlers: Dict[str, List[MessageHandler]] = {}
        self._pending: Dict[str, tuple] = {}  # msg_id -> (resolve_fn, timeout)
        self._history: List[Dict[str, Any]] = []
        self._max_history = 500

    # ---- 处理器注册 ----

    def on(self, action: str):
        """装饰器：注册消息处理器"""
        def decorator(handler: MessageHandler):
            self.register_handler(action, handler)
            return handler
        return decorator

    def register_handler(self, action: str, handler: MessageHandler):
        """注册消息处理器"""
        if action not in self._handlers:
            self._handlers[action] = []
        self._handlers[action].append(handler)
        logger.debug(f"[MessageBus] 注册处理器: {action}")

    def unregister_handler(self, action: str, handler: MessageHandler):
        """取消注册"""
        if action in self._handlers:
            self._handlers[action] = [
                h for h in self._handlers[action] if h is not handler
            ]

    # ---- 消息处理 ----

    def receive_from_js(self, raw_message: str) -> Optional[str]:
        """
        接收来自 JS 前端的消息（JSON 字符串）。
        返回 ACK 回执的 JSON 字符串，或 None（无需回复）。
        """
        try:
            msg = json.loads(raw_message) if isinstance(raw_message, str) else raw_message
        except json.JSONDecodeError:
            logger.warning("[MessageBus] 收到无效 JSON 消息")
            return self._build_ack(None, error="Invalid JSON")

        # 基础校验
        required = ["msg_id", "action"]
        for field in required:
            if field not in msg:
                logger.warning(f"[MessageBus] 消息缺少必要字段: {field}")
                return self._build_ack(msg.get("msg_id"), error=f"Missing field: {field}")

        action = msg["action"]
        payload = msg.get("payload", {})
        msg_id = msg["msg_id"]

        # 记录历史
        self._history.append(msg)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # 查找处理器
        handlers = self._handlers.get(action, [])
        if not handlers:
            logger.warning(f"[MessageBus] 未注册的 action: {action}")
            return self._build_ack(msg_id, error=f"Unknown action: {action}")

        # 执行处理器（取第一个返回值）
        try:
            result = None
            for handler in handlers:
                result = handler(payload)
                if result is not None:
                    break
            return self._build_ack(msg_id, data=result)
        except Exception as e:
            logger.error(f"[MessageBus] 处理器异常 {action}: {e}")
            return self._build_ack(msg_id, error=str(e))

    def send_to_js(self, action: str, payload: Any) -> str:
        """构建发送给 JS 前端的消息 JSON 字符串"""
        msg = {
            "msg_id": f"msg_{uuid.uuid4().hex[:8]}",
            "sender": "backend",
            "action": action,
            "payload": payload,
            "timestamp": int(time.time() * 1000),
        }
        self._history.append(msg)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        return json.dumps(msg, ensure_ascii=False)

    def broadcast_state(self, global_state_snapshot: Dict[str, Any]) -> str:
        """广播全局状态变更到前端"""
        return self.send_to_js("state_sync", global_state_snapshot)

    # ---- ACK ----

    def _build_ack(self, reply_to: Optional[str], data: Any = None, error: Optional[str] = None) -> str:
        """构建 ACK 回执消息"""
        ack = {
            "msg_id": f"ack_{uuid.uuid4().hex[:8]}",
            "sender": "backend",
            "action": "_ack",
            "payload": {
                "reply_to": reply_to,
                "data": data,
                "error": error,
            },
            "timestamp": int(time.time() * 1000),
        }
        return json.dumps(ack, ensure_ascii=False)

    # ---- 历史查询 ----

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取最近的消息历史"""
        return self._history[-limit:]

    def get_handlers(self) -> Dict[str, int]:
        """获取注册的处理器清单"""
        return {action: len(hs) for action, hs in self._handlers.items()}
