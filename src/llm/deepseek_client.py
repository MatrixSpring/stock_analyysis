import json
from src.llm.base_llm import BaseLLMClient
from src.config.settings import settings
from src.core.http_client import http_client
from src.core.exceptions import LLMServiceError
from src.core.logger import get_logger
from src.models.dto import LLMResultDTO

logger = get_logger()


class DeepSeekClient(BaseLLMClient):
    def __init__(self):
        self.api_key = settings.DEEPSEEK_API_KEY
        self.endpoint = settings.DEEPSEEK_ENDPOINT
        self.model = settings.DEEPSEEK_MODEL_ID
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def chat(
            self,
            prompt: str,
            system_prompt: str = "",
            temperature: float = 0.1
    ) -> LLMResultDTO:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        try:
            resp = http_client.post(
                url=f"{self.endpoint}/chat/completions",
                headers=self.headers,
                json=payload
            )
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data["usage"]
            return LLMResultDTO(
                content=content,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                model_name=self.model
            )
        except Exception as e:
            logger.error(f"DeepSeek调用失败 {str(e)}")
            raise LLMServiceError(f"DeepSeek API请求异常：{str(e)}") from e


deepseek_llm = DeepSeekClient()
