# -*- coding: utf-8 -*-
"""
===================================
LLM 调度网关 — llm/gateway.py
===================================

统一 LLM 调用入口，屏蔽底层模型差异。
功能：
- 任务自动路由：多模态→豆包，深度推演→DeepSeek
- 统一异常、限流、重试、日志
- 强制支持结构化 JSON 输出

路由规则：
  长新闻/复杂推演 (>2000字) → DeepSeek
  短新闻/轻量解析            → 豆包
  图片OCR识别               → 豆包（多模态）
  专业对话                  → DeepSeek
  轻量对话                  → 豆包

使用方式：
    from llm.gateway import LLMGateway
    gw = LLMGateway()
    result = gw.analyze_news("新闻文本...")
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

# 懒加载避免循环导入 (llm → core.utils → core.event_analyzer → llm)
_clean_llm_json = None
_retry = None

def _get_clean_llm_json():
    global _clean_llm_json
    if _clean_llm_json is None:
        from core.utils import clean_llm_json as fn
        _clean_llm_json = fn
    return _clean_llm_json

def _get_retry():
    global _retry
    if _retry is None:
        from core.utils import retry as fn
        _retry = fn
    return _retry

logger = logging.getLogger(__name__)


# ============================================================
# 类型定义
# ============================================================

class TaskType(Enum):
    NEWS_STRUCT_ANALYSIS = "news_struct_analysis"    # 新闻结构化解析
    CHAIN_SIMULATION = "chain_simulation"            # 产业链传导推演
    STOCK_DIAGNOSE = "stock_diagnose"                # 单标的多因子诊断
    AUDIT_REVISE = "audit_revise"                    # 审核修正
    IMAGE_OCR_NEWS = "image_ocr_news"                # 图片OCR识别
    CHAT_PROFESSIONAL = "chat_professional"          # 专业深度对话
    CHAT_LIGHT = "chat_light"                        # 轻量对话


class ModelProvider(Enum):
    DEEPSEEK = "deepseek"
    DOUBAO = "doubao"


@dataclass
class LLMResult:
    """LLM 调用结果"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    raw_text: Optional[str] = None
    model_used: str = ""
    latency_ms: float = 0.0
    token_count: int = 0
    error: Optional[str] = None


# ============================================================
# Prompt 加载器
# ============================================================

_PROMPT_DIR = Path(__file__).parent / "prompts"

_prompt_cache: Dict[str, str] = {}


def _load_prompt(name: str) -> str:
    """加载 Prompt 模板文件（带缓存）"""
    if name in _prompt_cache:
        return _prompt_cache[name]
    path = _PROMPT_DIR / f"{name}.prompt"
    if path.exists():
        content = path.read_text(encoding="utf-8")
        _prompt_cache[name] = content
        return content
    logger.warning(f"[LLMGateway] Prompt 文件不存在: {path}")
    return ""


# ============================================================
# LLM 调度网关
# ============================================================

class LLMGateway:
    """
    LLM 调度网关 — 统一调用入口。

    自动根据任务类型选择最优模型，封装
    """
    # JSON 强制后缀（追加到每个请求的 system prompt）
    JSON_FORCE_SUFFIX = (
        "\n\n=== 输出硬性约束 ===\n"
        "1. 仅返回纯净 JSON，不要任何额外文字、markdown标记、解释、换行备注\n"
        "2. 无法确认的信息填写 null，禁止编造\n"
        "3. 强度取值 1~10，方向只能是 positive/negative/neutral\n"
    )

    def __init__(self):
        self._model_cache: Dict[str, Any] = {}

    # ---- 任务路由 ----

    def route_task(self, task_type: TaskType, input_text: str = "") -> ModelProvider:
        """根据任务类型和输入自动选择模型"""
        if task_type == TaskType.IMAGE_OCR_NEWS:
            return ModelProvider.DOUBAO

        if task_type == TaskType.CHAT_LIGHT:
            return ModelProvider.DOUBAO

        if task_type == TaskType.CHAT_PROFESSIONAL:
            return ModelProvider.DEEPSEEK

        # 结构化解析：长文本 → DeepSeek, 短文本 → 豆包
        text_len = len(input_text) if input_text else 0
        if text_len > 2000:
            return ModelProvider.DEEPSEEK
        return ModelProvider.DOUBAO

    # ---- 主入口 ----

    def analyze_news(self, news_text: str) -> LLMResult:
        """
        新闻结构化解析（主入口）。
        用户粘贴新闻 → 返回标准化 JSON 用于驱动图谱和面板。
        """
        if not news_text or not news_text.strip():
            return LLMResult(success=False, error="新闻文本为空")

        provider = self.route_task(TaskType.NEWS_STRUCT_ANALYSIS, news_text)
        system_prompt = _load_prompt("news_analysis") + self.JSON_FORCE_SUFFIX
        user_prompt = f"待分析原文：\n{news_text}"

        return self._call_llm(provider, system_prompt, user_prompt, task="news_analysis")

    def simulate_chain(self, event_json: Dict, modified_chain: list) -> LLMResult:
        """产业链传导推演"""
        provider = ModelProvider.DEEPSEEK  # 复杂推演固定用 DeepSeek
        system_prompt = _load_prompt("chain_simulate") + self.JSON_FORCE_SUFFIX
        user_prompt = (
            f"输入事件信息：\n{json.dumps(event_json, ensure_ascii=False)}\n\n"
            f"当前人工调整后的传导链路：\n{json.dumps(modified_chain, ensure_ascii=False)}"
        )
        return self._call_llm(provider, system_prompt, user_prompt, task="chain_simulation")

    def diagnose_stock(self, stock_name: str, stock_code: str, event_pool: list) -> LLMResult:
        """单标的全景多因子诊断"""
        provider = ModelProvider.DEEPSEEK
        system_prompt = _load_prompt("stock_diagnose") + self.JSON_FORCE_SUFFIX
        user_prompt = (
            f"标的：{stock_name}({stock_code})\n"
            f"有效事件集合：\n{json.dumps(event_pool, ensure_ascii=False)}"
        )
        return self._call_llm(provider, system_prompt, user_prompt, task="stock_diagnose")

    def revise_audit(self, origin_json: Dict, user_modify: str) -> LLMResult:
        """审核修正"""
        provider = ModelProvider.DEEPSEEK
        system_prompt = _load_prompt("audit_revise") + self.JSON_FORCE_SUFFIX
        user_prompt = (
            f"原始AI推演结论：\n{json.dumps(origin_json, ensure_ascii=False)}\n\n"
            f"人工修改内容：\n{user_modify}"
        )
        return self._call_llm(provider, system_prompt, user_prompt, task="audit_revise")

    def chat(self, message: str, context: Dict, professional: bool = False) -> LLMResult:
        """对话面板"""
        provider = ModelProvider.DEEPSEEK if professional else ModelProvider.DOUBAO
        return self._call_llm(provider, message, json.dumps(context, ensure_ascii=False), task="chat")

    # ---- 新增：代码审查 ----

    def review_code(self, file_path: str, code: str) -> LLMResult:
        """AI 代码审查 — 检查逻辑漏洞、SQL 性能、安全性"""
        provider = ModelProvider.DOUBAO
        system_prompt = _load_prompt("code_review") + self.JSON_FORCE_SUFFIX
        user_prompt = f"文件路径：{file_path}\n\n代码内容：\n{code}"
        return self._call_llm(provider, system_prompt, user_prompt, task="code_review")

    # ---- 新增：K 线解读 ----

    def analyze_kline(self, stock_name: str, stock_code: str, kline_data: Dict) -> LLMResult:
        """K 线技术分析 — AI 解读技术指标"""
        provider = self.route_task(TaskType.STOCK_DIAGNOSE, str(kline_data))
        system_prompt = _load_prompt("kline_analysis") + self.JSON_FORCE_SUFFIX
        user_prompt = (
            f"标的：{stock_name}({stock_code})\n"
            f"K线数据：\n{json.dumps(kline_data, ensure_ascii=False)}"
        )
        return self._call_llm(provider, system_prompt, user_prompt, task="kline_analysis")

    # ---- 新增：自然语言选股 ----

    def screen_stocks(self, query: str) -> LLMResult:
        """自然语言选股 — 中文描述 → 量化筛选条件"""
        provider = ModelProvider.DOUBAO
        system_prompt = _load_prompt("stock_screening") + self.JSON_FORCE_SUFFIX
        user_prompt = f"选股需求：{query}"
        return self._call_llm(provider, system_prompt, user_prompt, task="stock_screening")

    # ---- 底层调用 ----

    def _call_llm(
        self, provider: ModelProvider, system_prompt: str, user_prompt: str, task: str = ""
    ) -> LLMResult:
        """底层 LLM 调用封装（带重试）"""
        for attempt in range(2):
            result = self._call_llm_once(provider, system_prompt, user_prompt, task)
            if result.success:
                return result
            if attempt < 1:
                time.sleep(1.0)
        return result

    def _call_llm_once(
        self, provider: ModelProvider, system_prompt: str, user_prompt: str, task: str = ""
    ) -> LLMResult:
        """单次 LLM 调用"""
        t0 = time.time()

        if provider == ModelProvider.DEEPSEEK:
            result = self._call_deepseek(system_prompt, user_prompt)
        else:
            result = self._call_doubao(system_prompt, user_prompt)

        latency_ms = (time.time() - t0) * 1000

        if not result.success:
            return result

        # JSON 清洗
        json_tasks = {"news_analysis", "chain_simulation", "stock_diagnose", "audit_revise", "code_review", "kline_analysis", "stock_screening"}
        if task in json_tasks:
            parsed = _get_clean_llm_json()(result.raw_text or "")
            if parsed is None:
                logger.warning(f"[LLMGateway] {task} JSON 解析失败，原始输出: {result.raw_text[:200]}")
                return LLMResult(
                    success=False,
                    raw_text=result.raw_text,
                    model_used=result.model_used,
                    latency_ms=latency_ms,
                    error="LLM 输出无法解析为 JSON，请精简输入文本后重试",
                )
            result.data = parsed

        result.latency_ms = latency_ms
        return result

    def _call_deepseek(self, system_prompt: str, user_prompt: str) -> LLMResult:
        """调用 DeepSeek API"""
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key:
            return LLMResult(success=False, error="未配置 DEEPSEEK_API_KEY")

        try:
            import litellm
            response = litellm.completion(
                model="deepseek/deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                api_key=api_key,
                temperature=0.3,
                max_tokens=4096,
                timeout=120,
            )
            content = response.choices[0].message.content or ""
            return LLMResult(
                success=True,
                raw_text=content,
                model_used="deepseek-chat",
                token_count=response.usage.total_tokens if response.usage else 0,
            )
        except Exception as e:
            logger.error(f"[LLMGateway] DeepSeek 调用失败: {e}")
            return LLMResult(success=False, model_used="deepseek-chat", error=str(e))

    def _call_doubao(self, system_prompt: str, user_prompt: str) -> LLMResult:
        """调用豆包 API（火山引擎 ARK）"""
        api_key = os.getenv("ARK_API_KEY", "")
        ark_model = os.getenv("ARK_MODEL", "")
        if not api_key:
            return LLMResult(success=False, error="未配置 ARK_API_KEY")

        try:
            import litellm
            response = litellm.completion(
                model=f"openai/{ark_model}",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                api_key=api_key,
                api_base="https://ark.cn-beijing.volces.com/api/v3",
                temperature=0.3,
                max_tokens=4096,
                timeout=120,
            )
            content = response.choices[0].message.content or ""
            return LLMResult(
                success=True,
                raw_text=content,
                model_used=ark_model,
                token_count=response.usage.total_tokens if response.usage else 0,
            )
        except Exception as e:
            logger.error(f"[LLMGateway] 豆包调用失败: {e}")
            return LLMResult(success=False, model_used="doubao-seed-code", error=str(e))


# 全局单例
_gateway_instance: Optional[LLMGateway] = None


def get_gateway() -> LLMGateway:
    """获取 LLM Gateway 全局单例"""
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = LLMGateway()
    return _gateway_instance
