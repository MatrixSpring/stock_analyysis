class BaseBusinessException(Exception):
    """项目基础业务异常"""
    code: int
    message: str

    def __init__(self, message: str, code: int = 500):
        self.message = message
        self.code = code
        super().__init__(self.message)


class DataQueryError(BaseBusinessException):
    """数据库查询异常"""


class HttpRequestError(BaseBusinessException):
    """外部HTTP请求异常"""


class LLMServiceError(BaseBusinessException):
    """LLM接口调用异常"""


class ParamValidateError(BaseBusinessException):
    """参数校验异常"""
