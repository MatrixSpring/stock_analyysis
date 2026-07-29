from src.core.exceptions import BaseBusinessException
from src.core.logger import get_logger

logger = get_logger()


def global_exception_handler(func):
    """统一异常捕获装饰器，UI页面、Service通用"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BaseBusinessException as e:
            logger.warning(f"业务异常 code={e.code} msg={e.message}")
            return {"success": False, "code": e.code, "msg": e.message, "data": None}
        except Exception as e:
            logger.exception("未知系统异常")
            return {"success": False, "code": 999, "msg": f"系统内部错误: {str(e)}", "data": None}
    return wrapper
