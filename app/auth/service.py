from sqlalchemy import select
from sqlalchemy.orm import Session

from app import tempo
from app.auth.models import Usuario
from app.auth.seguranca import hash_senha
from app.erros import ErroValidacao, NaoEncontrado

TAMANHO_MINIMO_SENHA = 8


def _normalizar_email(email: str) -> str:
    return email.strip().lower()


def _validar_senha(senha: str) -> None:
    if len(senha) < TAMANHO_MINIMO_SENHA:
        raise ErroValidacao(f"A senha precisa ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres.")


def buscar_por_email(db: Session, email: str) -> Usuario | None:
    return db.scalar(select(Usuario).where(Usuario.email == _normalizar_email(email)))


def _obter_por_email(db: Session, email: str) -> Usuario:
    usuario = buscar_por_email(db, email)
    if usuario is None:
        raise NaoEncontrado(f"Usuário não encontrado: {email}")
    return usuario


def criar_usuario(db: Session, email: str, nome: str, senha: str) -> Usuario:
    email = _normalizar_email(email)
    nome = nome.strip()
    if "@" not in email:
        raise ErroValidacao("Informe um email válido.")
    if not nome:
        raise ErroValidacao("Informe um nome.")
    _validar_senha(senha)
    if buscar_por_email(db, email) is not None:
        raise ErroValidacao("Já existe um usuário com este email.")
    usuario = Usuario(email=email, nome=nome, senha_hash=hash_senha(senha))
    db.add(usuario)
    db.commit()
    return usuario


def redefinir_senha(db: Session, email: str, senha: str) -> None:
    usuario = _obter_por_email(db, email)
    _validar_senha(senha)
    usuario.senha_hash = hash_senha(senha)
    db.commit()


def desativar_usuario(db: Session, email: str) -> None:
    usuario = _obter_por_email(db, email)
    usuario.ativo = False
    db.commit()


def atualizar_fuso(db: Session, usuario: Usuario, fuso: str) -> None:
    fuso = fuso.strip()
    if not tempo.fuso_valido(fuso):
        raise ErroValidacao("Fuso horário inválido.")
    usuario.fuso_horario = fuso
    db.commit()
