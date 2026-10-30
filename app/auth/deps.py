import secrets

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.models import Usuario
from app.db import get_db

COOKIE_SESSAO = "sessao"


class NaoAutenticado(Exception):
    pass


def usuario_atual(request: Request, db: Session = Depends(get_db)) -> Usuario:
    token = request.cookies.get(COOKIE_SESSAO)
    sessao = service.obter_sessao(db, token) if token else None
    if sessao is None:
        raise NaoAutenticado()
    request.state.sessao = sessao
    request.state.usuario = sessao.usuario
    return sessao.usuario


async def exigir_csrf(request: Request, usuario: Usuario = Depends(usuario_atual)) -> None:
    enviado = request.headers.get("X-CSRF-Token")
    if not enviado:
        formulario = await request.form()
        enviado = formulario.get("csrf_token")
    esperado = request.state.sessao.csrf_token
    if not isinstance(enviado, str) or not secrets.compare_digest(enviado, esperado):
        raise HTTPException(status_code=403, detail="Sessão inválida. Recarregue a página e tente de novo.")
