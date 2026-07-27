"""Конфигурация приложения (значения берутся из переменных окружения)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://grants:grants@db:5432/grants"

    # Аутентификация (п. 4.1.1 ТЗ: access 30 мин, refresh 7 суток)
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_ttl_min: int = 30
    refresh_token_ttl_days: int = 7

    # Публичный адрес фронтенда — для ссылок в письмах (FR-002, FR-009)
    public_url: str = "http://localhost:5173"


settings = Settings()
