from contextlib import contextmanager

import pytest
from sqlalchemy import select

from app import cli
from app.auth.models import Usuario
from app.auth.seguranca import verificar_senha


@pytest.fixture
def cli_no_banco_de_teste(db, monkeypatch):
    @contextmanager
    def abrir():
        yield db

    monkeypatch.setattr(cli, "abrir_sessao", abrir)


def _senhas(monkeypatch, *valores):
    fila = list(valores)
    monkeypatch.setattr(cli, "getpass", lambda prompt="": fila.pop(0))


def _buscar(db, email):
    return db.scalar(select(Usuario).where(Usuario.email == email))


def test_cli_criar_usuario(db, cli_no_banco_de_teste, monkeypatch):
    _senhas(monkeypatch, "senha-segura-1", "senha-segura-1")
    assert cli.main(["criar-usuario", "--email", "c@x.com", "--nome", "C"]) == 0
    u = _buscar(db, "c@x.com")
    assert u is not None and u.nome == "C"


def test_cli_senhas_diferentes_falha(db, cli_no_banco_de_teste, monkeypatch):
    _senhas(monkeypatch, "senha-segura-1", "senha-diferente")
    assert cli.main(["criar-usuario", "--email", "c@x.com", "--nome", "C"]) == 1
    assert _buscar(db, "c@x.com") is None


def test_cli_erro_de_validacao_retorna_1(db, cli_no_banco_de_teste, monkeypatch):
    _senhas(monkeypatch, "curta", "curta")
    assert cli.main(["criar-usuario", "--email", "c@x.com", "--nome", "C"]) == 1


def test_cli_redefinir_senha(db, usuario, cli_no_banco_de_teste, monkeypatch):
    _senhas(monkeypatch, "nova-senha-123", "nova-senha-123")
    assert cli.main(["redefinir-senha", "--email", "ana@example.com"]) == 0
    db.refresh(usuario)
    assert verificar_senha(usuario.senha_hash, "nova-senha-123")


def test_cli_desativar_usuario(db, usuario, cli_no_banco_de_teste):
    assert cli.main(["desativar-usuario", "--email", "ana@example.com"]) == 0
    db.refresh(usuario)
    assert usuario.ativo is False


def test_cli_desativar_inexistente_retorna_1(db, cli_no_banco_de_teste):
    assert cli.main(["desativar-usuario", "--email", "ninguem@x.com"]) == 1
