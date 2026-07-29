from pydantic import BaseModel
from typing import Generic, TypeVar, Optional

T = TypeVar("T")


class ApiResp(BaseModel, Generic[T]):
    success: bool
    code: int
    msg: str
    data: Optional[T] = None

    @classmethod
    def ok(cls, data: T = None, msg: str = "success"):
        return cls(success=True, code=200, msg=msg, data=data)

    @classmethod
    def fail(cls, code: int = 500, msg: str = "failed", data: T = None):
        return cls(success=False, code=code, msg=msg, data=data)
