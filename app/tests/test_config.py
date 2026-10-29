from config import Settings


def test_defaults_point_at_the_local_provider_with_conservative_limits():
    settings = Settings()

    assert settings.provider_base_url == "http://localhost:3001"
    assert settings.ai_max_retries == 1
    assert settings.notify_rate_per_s < 5
    assert settings.extraction_cache_enabled is False


def test_every_setting_can_be_overridden_from_the_environment(monkeypatch):
    monkeypatch.setenv("PROVIDER_BASE_URL", "http://provider:3001")
    monkeypatch.setenv("PROVIDER_API_KEY", "other-key")
    monkeypatch.setenv("WORKERS", "7")

    settings = Settings()

    assert settings.provider_base_url == "http://provider:3001"
    assert settings.provider_api_key == "other-key"
    assert settings.workers == 7
