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
    cors_origins: str = (
        "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001"
    )
    json_logs: bool = True
    llm_provider: str = "demo"
    llm_model: str = "gpt-4o-mini"
    embedding_dim: int = 128
    vector_backend: str = "memory"
    corpus_dir: str = "docs/corpus"
    max_iterations: int = 3
    rag_max_iterations: int = 3
    graph_timeout_seconds: float = 30.0
    auto_migrate: bool = False
    seed_on_start: bool = False
    db_wait_seconds: float = 60.0
    session_ttl_hours: int = 72
    cookie_name: str = "payintel_session"
    cookie_secure: bool = False
    password_min_length: int = 10
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""
    bootstrap_admin_name: str = "PayIntel Admin"
    public_app_url: str = "http://localhost:3001"
    reset_token_ttl_minutes: int = 60
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def session_cookie_secure(self) -> bool:
        if self.cookie_secure:
            return True
        return self.environment not in {"local", "test"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
