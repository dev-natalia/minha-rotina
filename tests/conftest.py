import os
import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

URL_TESTE = os.environ.get("TEST_DATABASE_URL")
if not URL_TESTE:
    raise RuntimeError("Defina TEST_DATABASE_URL (veja .env.example).")

# Toda a aplicação usa o banco de teste durante a suíte.
os.environ["DATABASE_URL"] = URL_TESTE


@pytest.fixture(scope="session")
def engine_teste():
    cfg = Config(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ / "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(URL_TESTE)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine_teste):
    conexao = engine_teste.connect()
    transacao = conexao.begin()
    sessao = Session(bind=conexao, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield sessao
    finally:
        sessao.close()
        transacao.rollback()
        conexao.close()


SENHA_TESTE = "senha-segura-1"


@pytest.fixture
def usuario(db):
    from app.auth.service import criar_usuario

    return criar_usuario(db, "ana@example.com", "Ana", SENHA_TESTE)


@pytest.fixture
def outro_usuario(db):
    from app.auth.service import criar_usuario

    return criar_usuario(db, "bia@example.com", "Bia", SENHA_TESTE)


@pytest.fixture
def cliente(db):
    from app.db import get_db
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c


def ler_csrf(html: str) -> str:
    achado = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
    assert achado, "página sem meta csrf-token"
    return achado.group(1)


def entrar(cliente, email: str, senha: str = SENHA_TESTE):
    r = cliente.post("/login", data={"email": email, "senha": senha}, follow_redirects=False)
    assert r.status_code == 303, r.text
    cliente.csrf = ler_csrf(cliente.get("/conta").text)
    return cliente


@pytest.fixture
def cliente_logado(cliente, usuario):
    return entrar(cliente, usuario.email)


@pytest.fixture
def post():
    def _post(cliente, url: str, dados: dict | None = None, htmx: bool = False, **kwargs):
        dados = {"csrf_token": cliente.csrf, **(dados or {})}
        headers = {"HX-Request": "true"} if htmx else {}
        kwargs.setdefault("follow_redirects", False)
        return cliente.post(url, data=dados, headers=headers, **kwargs)

    return _post
