from abc import ABC, abstractmethod
from src.models.dto import LLMResultDTO


class BaseLLMClient(ABC):
    @abstractmethod
    def chat(
            self,
            prompt: str,
            system_prompt: str = "",
            temperature: float = 0.1
    ) -> LLMResultDTO:
        pass
