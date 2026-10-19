import pytest

from app.auth import service
from app.auth.seguranca import verificar_senha
from app.erros import ErroValidacao, NaoEncontrado


def test_criar_usuario_normaliza_email(db):
    u = service.criar_usuario(db, " Ana@Example.COM ", "Ana", "senha-segura-1")
    assert u.email == "ana@example.com"
    assert u.senha_hash != "senha-segura-1"
    assert verificar_senha(u.senha_hash, "senha-segura-1")
    assert u.fuso_horario == "America/Sao_Paulo"
    assert u.ativo is True


def test_email_duplicado_erro(db):
    service.criar_usuario(db, "ana@example.com", "Ana", "senha-segura-1")
    with pytest.raises(ErroValidacao, match="Já existe um usuário com este email."):
        service.criar_usuario(db, "ANA@example.com", "Outra", "senha-segura-2")


def test_senha_curta_erro(db):
    with pytest.raises(ErroValidacao):
        service.criar_usuario(db, "ana@example.com", "Ana", "1234567")


def test_email_invalido_e_nome_vazio(db):
    with pytest.raises(ErroValidacao):
        service.criar_usuario(db, "sem-arroba", "Ana", "senha-segura-1")
    with pytest.raises(ErroValidacao):
        service.criar_usuario(db, "ana@example.com", "   ", "senha-segura-1")


def test_redefinir_senha(db, usuario):
    service.redefinir_senha(db, "ana@example.com", "outra-senha-boa")
    db.refresh(usuario)
    assert verificar_senha(usuario.senha_hash, "outra-senha-boa")
    assert not verificar_senha(usuario.senha_hash, "senha-segura-1")


def test_redefinir_senha_email_inexistente(db):
    with pytest.raises(NaoEncontrado):
        service.redefinir_senha(db, "ninguem@example.com", "outra-senha-boa")


def test_desativar_usuario(db, usuario):
    service.desativar_usuario(db, "ana@example.com")
    db.refresh(usuario)
    assert usuario.ativo is False


def test_atualizar_fuso(db, usuario):
    service.atualizar_fuso(db, usuario, "America/Manaus")
    assert usuario.fuso_horario == "America/Manaus"


def test_atualizar_fuso_invalido(db, usuario):
    with pytest.raises(ErroValidacao, match="Fuso horário inválido."):
        service.atualizar_fuso(db, usuario, "Marte/Base")
