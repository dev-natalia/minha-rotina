from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    cookie_secure: bool = True
    dias_sessao: int = 90
    ambiente: str = "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
