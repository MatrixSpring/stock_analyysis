from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from src.api.response import ApiResp
from src.llm import LLMFactory
from src.core.logger import get_logger

router = APIRouter(prefix="/llm", tags=["AI分析接口"])
logger = get_logger()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    prompt: str
    system_prompt: str = ""
    model_type: str = "doubao"
    temperature: float = 0.4
    history: Optional[List[ChatMessage]] = None


@router.post("/chat", summary="AI对话 - 支持豆包/DeepSeek双模型切换")
async def chat(req: ChatRequest):
    client = LLMFactory.get_client(req.model_type)

    # 构建带历史上下文的 prompt
    full_prompt = req.prompt
    if req.history:
        context_parts = []
        for msg in req.history[-10:]:  # 最近10轮
            prefix = "用户" if msg.role == "user" else "AI"
            context_parts.append(f"{prefix}: {msg.content}")
        context_parts.append(f"用户: {req.prompt}")
        full_prompt = "\n".join(context_parts)

    result = client.chat(
        full_prompt,
        system_prompt=req.system_prompt,
        temperature=req.temperature,
    )

    return ApiResp.ok(data={
        "content": result.content,
        "model_name": result.model_name,
        "model_type": req.model_type,
        "tokens": result.prompt_tokens + result.completion_tokens,
    })


@router.get("/health", summary="LLM服务健康检查")
async def llm_health():
    return ApiResp.ok(data={"status": "available", "doubao": True, "deepseek": True})
