from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (or a local .env file)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    provider_base_url: str = "http://localhost:3001"
    # The challenge's public test key: the given docker-compose passes no environment to the app
    provider_api_key: str = "test-dev-2026"

    # Concurrent pipeline workers; each one handles one request at a time
    workers: int = 50
    # Bound on requests waiting to be processed, to protect memory
    queue_max_size: int = 10_000

    ai_timeout_s: float = 10.0
    # One retry at most: dirty JSON is repaired by the guardrails, never by asking again
    ai_max_retries: int = 1
    # Off by default: the load test repeats four sentences, so a cache would hide the real extraction cost
    extraction_cache_enabled: bool = False

    notify_timeout_s: float = 5.0
    # The provider allows 50 calls per sliding 10 s window; staying under 5/s avoids provoking 429s
    notify_rate_per_s: float = 4.5
    notify_max_attempts: int = 3


settings = Settings()
