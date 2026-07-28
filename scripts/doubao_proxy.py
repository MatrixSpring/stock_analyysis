#!/usr/bin/env python3
"""
============================================================
豆包 API 代理 — Anthropic Messages API → OpenAI Chat Completions
============================================================

将 Claude Code 的 Anthropic-format 请求翻译为豆包 OpenAI-format 请求。
启动后 Claude Code 通过 ANTHROPIC_BASE_URL=http://127.0.0.1:4000 接入。

使用方式：
  python scripts/doubao_proxy.py --port 4000
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("doubao-proxy")

ARK_API_KEY = os.getenv("ARK_API_KEY", "")
ARK_API_BASE = os.getenv("ARK_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")
ARK_MODEL = os.getenv("ARK_MODEL", "ep-20260728220441-fnn2g")

# ============================================================
# Anthropic → OpenAI 格式转换
# ============================================================

def anthropic_to_openai(anth_body: dict) -> dict:
    """Translate Anthropic Messages request → OpenAI Chat Completions request."""
    messages = []
    system_msg = ""

    # System prompt
    if "system" in anth_body:
        sys = anth_body["system"]
        if isinstance(sys, str):
            system_msg = sys
        elif isinstance(sys, list):
            system_msg = "\n".join(
                item.get("text", "") for item in sys
                if isinstance(item, dict) and item.get("type") == "text"
            )

    # Messages
    for msg in anth_body.get("messages", []):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif isinstance(block, dict) and block.get("type") == "tool_use":
                    text_parts.append(
                        f"[Tool Call: {block.get('name', 'unknown')}]\n"
                        f"Input: {json.dumps(block.get('input', {}), ensure_ascii=False)}"
                    )
                elif isinstance(block, dict) and block.get("type") == "tool_result":
                    text_parts.append(
                        f"[Tool Result: {block.get('tool_use_id', '')}]\n"
                        f"{block.get('content', '')}"
                    )
            content = "\n".join(text_parts)
        messages.append({"role": role, "content": content})

    # Inject system prompt as first user message if present
    if system_msg and messages:
        messages.insert(0, {"role": "system", "content": system_msg})

    openai_body = {
        "model": ARK_MODEL,
        "messages": messages,
        "max_tokens": anth_body.get("max_tokens", 4096),
        "temperature": anth_body.get("temperature", 0.3),
    }

    if anth_body.get("stop_sequences"):
        openai_body["stop"] = anth_body["stop_sequences"]
    if anth_body.get("top_p"):
        openai_body["top_p"] = anth_body["top_p"]

    # Handle tools
    if anth_body.get("tools"):
        openai_body["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": t.get("name", ""),
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {}),
                },
            }
            for t in anth_body["tools"]
        ]
        # Check if tool_choice is specified
        if anth_body.get("tool_choice"):
            tc = anth_body["tool_choice"]
            if isinstance(tc, dict) and tc.get("type") == "tool":
                openai_body["tool_choice"] = {
                    "type": "function",
                    "function": {"name": tc.get("name", "")},
                }
            elif tc == "any":
                openai_body["tool_choice"] = "auto"
            elif tc == "auto":
                openai_body["tool_choice"] = "auto"

    return openai_body


def openai_to_anthropic(openai_resp: dict, model: str = "doubao-seed-code") -> dict:
    """Translate OpenAI Chat Completions response → Anthropic Messages response."""
    choice = openai_resp.get("choices", [{}])[0]
    message = choice.get("message", {})
    content = message.get("content", "")
    tool_calls = message.get("tool_calls", [])

    # Build Anthropic content blocks
    content_blocks = []
    if content:
        content_blocks.append({"type": "text", "text": content})

    # Translate tool calls
    for tc in tool_calls:
        fn = tc.get("function", {})
        try:
            arguments = json.loads(fn.get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError):
            arguments = {"raw": fn.get("arguments", "{}")}
        content_blocks.append({
            "type": "tool_use",
            "id": tc.get("id", f"call_{int(time.time())}"),
            "name": fn.get("name", ""),
            "input": arguments,
        })

    stop_reason = choice.get("finish_reason", "end_turn")
    if stop_reason == "stop":
        stop_reason = "end_turn"
    elif stop_reason == "tool_calls":
        stop_reason = "tool_use"
    elif stop_reason == "length":
        stop_reason = "max_tokens"

    usage = openai_resp.get("usage", {})

    return {
        "id": f"msg_{int(time.time() * 1000)}",
        "type": "message",
        "role": "assistant",
        "content": content_blocks,
        "model": model,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


def openai_stream_to_anthropic_sse(chunk: dict, model: str) -> str | None:
    """Convert one OpenAI streaming chunk to Anthropic SSE event string. Returns None for empty chunks."""
    choice = chunk.get("choices", [{}])[0]
    delta = choice.get("delta", {})
    finish_reason = choice.get("finish_reason")

    if finish_reason:
        return None  # Final chunk handled separately

    content = delta.get("content", "")
    if not content:
        return None

    event = {
        "type": "content_block_delta",
        "index": 0,
        "delta": {
            "type": "text_delta",
            "text": content,
        },
    }
    return f"event: content_block_delta\ndata: {json.dumps(event)}\n\n"


# ============================================================
# HTTP Handler
# ============================================================

class ProxyHandler(BaseHTTPRequestHandler):
    """HTTP handler that translates Anthropic ↔ OpenAI formats."""

    def log_message(self, fmt, *args):
        logger.info(fmt % args)

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_sse(self, generator):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_POST(self):
        path = self.path.rstrip("/")

        if path == "/v1/messages" or path == "/v1/messages/stream":
            self._handle_messages()
        elif path == "/v1/chat/completions":
            self._passthrough_openai()
        elif path == "/health":
            self._send_json({"status": "ok"})
        else:
            self._send_json({"error": f"Unknown path: {path}"}, 404)

    def do_GET(self):
        path = self.path.rstrip("/")
        if path == "/health" or path == "" or path == "/":
            self._send_json({"status": "ok", "model": ARK_MODEL, "proxy": "doubao"})
        elif path == "/v1/models":
            self._send_json({
                "data": [{"id": ARK_MODEL, "object": "model", "type": "language"}]
            })
        else:
            self._send_json({"error": f"Unknown path: {path}"}, 404)

    def _handle_messages(self):
        """Handle Anthropic Messages API request."""
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)
        try:
            anth_body = json.loads(raw_body)
        except json.JSONDecodeError as e:
            self._send_json({"error": f"Invalid JSON: {e}"}, 400)
            return

        stream = anth_body.get("stream", False)

        try:
            openai_body = anthropic_to_openai(anth_body)
        except Exception as e:
            logger.error(f"Translation error: {e}")
            self._send_json({"error": f"Translation error: {e}"}, 500)
            return

        logger.info(
            f"→ {ARK_MODEL} | {len(openai_body.get('messages', []))} msgs | "
            f"stream={stream} | tools={len(anth_body.get('tools', []))}"
        )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ARK_API_KEY}",
        }

        if stream:
            openai_body["stream"] = True
            self._proxy_stream(openai_body, headers)
        else:
            self._proxy_sync(openai_body, headers, anth_body.get("model", ARK_MODEL))

    def _proxy_sync(self, openai_body: dict, headers: dict, model: str):
        """Non-streaming proxy call."""
        try:
            req = Request(
                f"{ARK_API_BASE}/chat/completions",
                data=json.dumps(openai_body).encode("utf-8"),
                headers=headers,
            )
            resp = urlopen(req, timeout=120)
            result = json.loads(resp.read().decode("utf-8"))
            anth_resp = openai_to_anthropic(result, model)
            logger.info(f"← {model} | {anth_resp['usage'].get('input_tokens', '?')}/{anth_resp['usage'].get('output_tokens', '?')} tokens")
            self._send_json(anth_resp)
        except HTTPError as e:
            err_body = e.read().decode("utf-8") if e.fp else str(e)
            logger.error(f"ARK API error ({e.code}): {err_body[:300]}")
            try:
                err_json = json.loads(err_body)
            except json.JSONDecodeError:
                err_json = {"error": {"message": err_body[:500]}}
            self._send_json({
                "type": "error",
                "error": {
                    "type": "api_error",
                    "message": err_json.get("error", {}).get("message", str(e)),
                },
            }, e.code or 500)
        except URLError as e:
            logger.error(f"Connection error: {e}")
            self._send_json({
                "type": "error",
                "error": {"type": "connection_error", "message": str(e.reason)},
            }, 502)

    def _proxy_stream(self, openai_body: dict, headers: dict):
        """Streaming SSE proxy call."""
        self._send_sse(None)

        try:
            req = Request(
                f"{ARK_API_BASE}/chat/completions",
                data=json.dumps(openai_body).encode("utf-8"),
                headers=headers,
            )
            resp = urlopen(req, timeout=180)

            # Send message_start event
            msg_start = json.dumps({
                "type": "message_start",
                "message": {"id": f"msg_{int(time.time() * 1000)}", "type": "message", "role": "assistant", "model": ARK_MODEL},
            })
            self.wfile.write(f"event: message_start\ndata: {msg_start}\n\n".encode())
            self.wfile.flush()

            # Read SSE stream from ARK
            buffer = ""
            for chunk in resp:
                buffer += chunk.decode("utf-8")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            sse = openai_stream_to_anthropic_sse(data, ARK_MODEL)
                            if sse:
                                self.wfile.write(sse.encode())
                                self.wfile.flush()
                        except json.JSONDecodeError:
                            continue

            # Send message_stop event
            msg_stop = json.dumps({"type": "message_stop"})
            self.wfile.write(f"event: message_stop\ndata: {msg_stop}\n\n".encode())
            self.wfile.flush()
            logger.info(f"← stream complete")

        except HTTPError as e:
            err_body = e.read().decode("utf-8")[:500] if e.fp else str(e)
            logger.error(f"ARK stream error ({e.code}): {err_body}")
            error_event = json.dumps({
                "type": "error",
                "error": {"type": "api_error", "message": err_body},
            })
            self.wfile.write(f"event: error\ndata: {error_event}\n\n".encode())
        except URLError as e:
            logger.error(f"Stream connection error: {e}")
            error_event = json.dumps({
                "type": "error",
                "error": {"type": "connection_error", "message": str(e.reason)},
            })
            self.wfile.write(f"event: error\ndata: {error_event}\n\n".encode())

    def _passthrough_openai(self):
        """Direct passthrough for OpenAI-format requests."""
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ARK_API_KEY}",
        }
        try:
            req = Request(
                f"{ARK_API_BASE}/chat/completions",
                data=raw_body,
                headers=headers,
            )
            resp = urlopen(req, timeout=120)
            body = resp.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except HTTPError as e:
            err_body = e.read() if e.fp else b"{}"
            self.send_response(e.code or 500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(err_body)


def main():
    parser = argparse.ArgumentParser(description="Doubao API Proxy for Claude Code")
    parser.add_argument("--port", type=int, default=4000, help="Proxy port (default: 4000)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════════╗
║     豆包 API 代理 — Claude Code 适配器       ║
╠══════════════════════════════════════════════╣
║  Model:  {ARK_MODEL:<36} ║
║  API:    https://ark.cn-beijing.volces.com  ║
║  Proxy:  http://{args.host}:{args.port:<5}                   ║
╚══════════════════════════════════════════════╝

  在 Claude Code 中设置：
    export ANTHROPIC_BASE_URL="http://{args.host}:{args.port}"
    export ANTHROPIC_API_KEY="sk-litellm-local"
""")

    server = HTTPServer((args.host, args.port), ProxyHandler)
    try:
        logger.info(f"Starting proxy on {args.host}:{args.port}")
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
