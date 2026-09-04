from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PAYOPS_", extra="ignore")

    database_url: str = "sqlite:///./data/local/payops.db"
    llm_provider: str = "demo"
    llm_model: str = "gpt-4o-mini"
    vector_dir: str = "./data/local/chroma"
    embedding_provider: str = "lexical"
    max_iterations: int = 3
    max_critic_revisions: int = 1
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def corpus_dir(self) -> Path:
        return ROOT / "docs" / "corpus"


@lru_cache
def get_settings() -> Settings:
    return Settings()
