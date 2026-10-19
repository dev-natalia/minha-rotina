from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    cookie_secure: bool = True
    dias_sessao: int = 90
    ambiente: str = "dev"

    @field_validator("database_url")
    @classmethod
    def _usar_psycopg(cls, url: str) -> str:
        """Aceita a URL como o Neon a mostra (postgresql://...) e usa o driver psycopg."""
        for prefixo in ("postgresql://", "postgres://"):
            if url.startswith(prefixo):
                return "postgresql+psycopg://" + url[len(prefixo):]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
