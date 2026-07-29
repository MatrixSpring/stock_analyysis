from fastapi import Request
from fastapi.responses import JSONResponse
from src.core.exceptions import BaseBusinessException
from src.core.logger import get_logger
from src.api.response import ApiResp

logger = get_logger()


async def global_exception_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except BaseBusinessException as e:
        logger.warning(f"业务异常 code={e.code} msg={e.message}")
        return JSONResponse(content=ApiResp.fail(code=e.code, msg=e.message).model_dump())
    except Exception as e:
        logger.exception("服务未知异常")
        return JSONResponse(content=ApiResp.fail(code=999, msg=f"服务器异常：{str(e)}").model_dump())
