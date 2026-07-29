"""统一依赖管理，方便未来增加鉴权、限流"""
from fastapi import Depends


# 预留：后续可以实现token鉴权、接口限流
async def common_auth():
    # 预留鉴权逻辑
    return True
