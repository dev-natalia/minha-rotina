from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import tempo
from app.auth import service
from app.auth.deps import COOKIE_SESSAO, exigir_csrf, usuario_atual
from app.auth.models import Usuario
from app.config import get_settings
from app.db import get_db
from app.erros import ErroValidacao
from app.web import render

router = APIRouter()


@router.get("/login")
def pagina_login(request: Request):
    return render(request, "auth/login.html", {"email": ""})


@router.post("/login")
def fazer_login(
    request: Request,
    email: str = Form(""),
    senha: str = Form(""),
    db: Session = Depends(get_db),
):
    ip = request.client.host if request.client else "desconhecido"
    try:
        usuario = service.autenticar(db, email, senha, ip)
    except service.MuitasTentativas:
        return render(
            request, "auth/login.html",
            {"email": email, "erro": "Muitas tentativas. Tente de novo em alguns minutos."}, status=429,
        )
    if usuario is None:
        return render(request, "auth/login.html", {"email": email, "erro": "Email ou senha incorretos."}, status=400)

    token, _ = service.criar_sessao(db, usuario)
    settings = get_settings()
    resposta = RedirectResponse("/", status_code=303)
    resposta.set_cookie(
        COOKIE_SESSAO, token,
        max_age=settings.dias_sessao * 86400,
        httponly=True, secure=settings.cookie_secure, samesite="lax",
    )
    return resposta


@router.post("/sair", dependencies=[Depends(exigir_csrf)])
def sair(request: Request, db: Session = Depends(get_db)):
    service.encerrar_sessao(db, request.cookies.get(COOKIE_SESSAO, ""))
    resposta = RedirectResponse("/login", status_code=303)
    resposta.delete_cookie(COOKIE_SESSAO)
    return resposta


@router.get("/conta")
def pagina_conta(request: Request, usuario: Usuario = Depends(usuario_atual)):
    return render(request, "conta/conta.html", {"fuso_digitado": usuario.fuso_horario})


@router.post("/conta/fuso", dependencies=[Depends(exigir_csrf)])
def trocar_fuso(
    request: Request,
    fuso_horario: str = Form(""),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    try:
        service.atualizar_fuso(db, usuario, fuso_horario)
    except ErroValidacao as erro:
        return render(
            request, "conta/conta.html",
            {"fuso_digitado": fuso_horario, "erro": erro.mensagem}, status=400,
        )
    return RedirectResponse("/conta?salvo=1", status_code=303)
