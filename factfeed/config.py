from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://factfeed:factfeed@localhost:5432/factfeed"
    debug: bool = False

    # Ingestion settings
    ingest_interval_minutes: int = 15
    user_agent: str = "FactFeed/1.0 RSS reader"
    article_fetch_delay: float = 1.5
    consecutive_failure_threshold: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
