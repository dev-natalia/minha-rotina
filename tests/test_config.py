import pytest

from app.config import Settings


@pytest.mark.parametrize("url, esperado", [
    # URL copiada do painel do Neon: precisa do driver psycopg.
    ("postgresql://u:s@ep-x.neon.tech/rotina?sslmode=require",
     "postgresql+psycopg://u:s@ep-x.neon.tech/rotina?sslmode=require"),
    ("postgres://u:s@host/db", "postgresql+psycopg://u:s@host/db"),
    ("postgresql+psycopg://u:s@host/db", "postgresql+psycopg://u:s@host/db"),
])
def test_database_url_aceita_formato_do_neon(url, esperado):
    assert Settings(database_url=url).database_url == esperado
