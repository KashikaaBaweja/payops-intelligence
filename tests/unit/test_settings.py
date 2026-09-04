from payops_core.config import Settings, get_settings


def test_default_settings(monkeypatch) -> None:
    monkeypatch.delenv("PAYOPS_ENVIRONMENT", raising=False)
    get_settings.cache_clear()
    settings = Settings(_env_file=None)
    assert settings.api_port == 8000
    assert settings.cors_origin_list == ["http://localhost:3000"]
    get_settings.cache_clear()


def test_cors_split() -> None:
    settings = Settings(cors_origins="http://a.test, http://b.test", _env_file=None)
    assert settings.cors_origin_list == ["http://a.test", "http://b.test"]
