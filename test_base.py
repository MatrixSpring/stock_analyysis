"""
执行命令：python test_base.py
用于校验整套基座是否正常运行
"""
from src.config.settings import settings
from src.core.logger import get_logger
from src.db.base_repo import BaseRepo
from src.llm.doubao_client import doubao_llm

logger = get_logger()

def test_config():
    logger.info("=== 测试配置加载 ===")
    logger.info(f"DB_PATH: {settings.DB_PATH}")
    logger.info(f"ENV: {settings.APP_ENV}")
    logger.info("配置加载成功")


def test_db_conn():
    logger.info("=== 测试数据库连接 ===")
    repo = BaseRepo()
    df = repo.query_df("SELECT 1 as test")
    logger.info(f"数据库连通测试结果: {df.iloc[0]['test']}")


if __name__ == "__main__":
    test_config()
    test_db_conn()
    logger.info("✅ 基础基座全部校验通过，可以开始开发DB仓储与Service")
