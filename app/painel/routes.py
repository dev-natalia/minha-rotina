from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app import tempo
from app.auth.deps import usuario_atual
from app.auth.models import Usuario
from app.contadores import service as contadores
from app.contadores.routes import contexto_cartoes
from app.db import get_db
from app.rotina import service as rotina
from app.rotina.models import AtividadePlanejada
from app.web import render

router = APIRouter()

EstadoAtividade = Literal["passada", "agora", "futura"]


def saudacao(hora_local: int) -> str:
    if 5 <= hora_local < 12:
        return "Bom dia"
    if 12 <= hora_local < 18:
        return "Boa tarde"
    return "Boa noite"


def estado_atividade(atividade: AtividadePlanejada, agora_local: datetime) -> EstadoAtividade:
    agora = agora_local.replace(tzinfo=None)
    inicio = datetime.combine(atividade.data, atividade.hora_inicio)
    fim = datetime.combine(atividade.data, atividade.hora_fim)
    if agora >= fim:
        return "passada"
    if agora >= inicio:
        return "agora"
    return "futura"


@router.get("/")
def painel(request: Request, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    agora_local = tempo.local(tempo.agora_utc(), usuario.fuso_horario)
    hoje = agora_local.date()
    atividades = rotina.listar_dia(db, usuario.id, hoje)
    ativos = contadores.listar_contadores(db, usuario.id)
    return render(request, "painel/painel.html", {
        "data_extenso": tempo.data_por_extenso(hoje),
        "saudacao": saudacao(agora_local.hour),
        "atividades": [(a, estado_atividade(a, agora_local)) for a in atividades],
        "contadores": ativos,
        "periodo": "dia",
        "voltar": "/",
        **contexto_cartoes(db, usuario, "dia", ativos),
    })
