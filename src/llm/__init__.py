from src.llm.base_llm import BaseLLMClient
from src.llm.doubao_client import doubao_llm
from src.llm.deepseek_client import deepseek_llm
from src.config.settings import settings


class LLMFactory:
    @staticmethod
    def get_client(model_type: str = "doubao") -> BaseLLMClient:
        """
        model_type: doubao / deepseek
        """
        match model_type.lower():
            case "doubao":
                return doubao_llm
            case "deepseek":
                return deepseek_llm
            case _:
                raise ValueError(f"不支持的模型类型 {model_type}")


# 全局默认实例
llm_client = LLMFactory.get_client("doubao")


__all__ = ["BaseLLMClient", "LLMFactory", "llm_client", "doubao_llm", "deepseek_llm"]
