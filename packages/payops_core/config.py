from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and optional `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PAYOPS_",
        extra="ignore",
    )

    environment: str = "local"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./data/local/payops.db"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"
    llm_provider: str = "demo"
    llm_model: str = "gpt-4o-mini"
    embedding_dim: int = 128
    vector_backend: str = "memory"
    corpus_dir: str = "docs/corpus"
    max_iterations: int = 3
    graph_timeout_seconds: float = 30.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
