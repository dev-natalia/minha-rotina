import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import tempo
from app.auth.models import Sessao, TentativaLogin, Usuario
from app.auth.seguranca import hash_senha, verificar_senha
from app.config import get_settings
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


# --- Login e sessão -------------------------------------------------------

LIMITE_FALHAS_EMAIL = 5
LIMITE_FALHAS_IP = 20
JANELA_FALHAS = timedelta(minutes=15)


class MuitasTentativas(Exception):
    pass


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def autenticar(db: Session, email: str, senha: str, ip: str) -> Usuario | None:
    email = _normalizar_email(email)
    agora = tempo.agora_utc()
    desde = agora - JANELA_FALHAS
    falhas_email = db.scalar(
        select(func.count()).where(TentativaLogin.email == email, TentativaLogin.criado_em > desde)
    )
    falhas_ip = db.scalar(
        select(func.count()).where(TentativaLogin.ip == ip, TentativaLogin.criado_em > desde)
    )
    if falhas_email >= LIMITE_FALHAS_EMAIL or falhas_ip >= LIMITE_FALHAS_IP:
        raise MuitasTentativas()

    usuario = buscar_por_email(db, email)
    if usuario is not None and usuario.ativo and verificar_senha(usuario.senha_hash, senha):
        return usuario
    db.add(TentativaLogin(email=email, ip=ip, criado_em=agora))
    db.commit()
    return None


def criar_sessao(db: Session, usuario: Usuario) -> tuple[str, Sessao]:
    token = secrets.token_urlsafe(32)
    sessao = Sessao(
        token_hash=_hash_token(token),
        usuario_id=usuario.id,
        csrf_token=secrets.token_urlsafe(32),
        expira_em=tempo.agora_utc() + timedelta(days=get_settings().dias_sessao),
    )
    db.add(sessao)
    db.commit()
    return token, sessao


def obter_sessao(db: Session, token: str) -> Sessao | None:
    sessao = db.scalar(select(Sessao).where(Sessao.token_hash == _hash_token(token)))
    agora = tempo.agora_utc()
    if sessao is None or sessao.expira_em <= agora or not sessao.usuario.ativo:
        return None
    duracao = timedelta(days=get_settings().dias_sessao)
    # Renova no máximo uma vez por dia para não escrever no banco a cada request.
    if sessao.expira_em < agora + duracao - timedelta(days=1):
        sessao.expira_em = agora + duracao
        db.commit()
    return sessao


def encerrar_sessao(db: Session, token: str) -> None:
    db.execute(delete(Sessao).where(Sessao.token_hash == _hash_token(token)))
    db.commit()
