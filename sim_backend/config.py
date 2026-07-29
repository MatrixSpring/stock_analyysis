from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    NEO4J_URI: str = "bolt://127.0.0.1:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    # SQLite fallback 模式：Neo4j 不可用时自动降级
    USE_NEO4J: bool = False


settings = Settings()
