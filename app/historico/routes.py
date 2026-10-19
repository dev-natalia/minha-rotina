from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import tempo
from app.auth.deps import exigir_csrf, usuario_atual
from app.auth.models import Usuario
from app.contadores import lancamentos, service
from app.contadores.lancamentos import TotalGrupo
from app.contadores.models import Lancamento
from app.contadores.service import ler_inteiro
from app.db import get_db
from app.erros import ErroValidacao
from app.web import render

router = APIRouter(prefix="/historico")

AGRUPAMENTOS = (("dia", "Dia"), ("mes", "Mês"), ("ano", "Ano"))
DIAS_PADRAO = 30
_MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho",
          "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")
_DIAS_CURTOS = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")


def rotulo_grupo(grupo: TotalGrupo, agrupar: str) -> str:
    d = grupo.inicio
    if agrupar == "mes":
        return f"{_MESES[d.month - 1]} de {d.year}"
    if agrupar == "ano":
        return str(d.year)
    return f"{d.day:02d}/{d.month:02d} ({_DIAS_CURTOS[d.weekday()]})"


def _ler_data(texto: str | None) -> date | None:
    try:
        return date.fromisoformat(texto) if texto else None
    except ValueError:
        return None


def _momento_local(data: str, hora: str, fuso: str) -> datetime:
    try:
        return datetime.combine(date.fromisoformat(data.strip()), time.fromisoformat(hora.strip()), tzinfo=ZoneInfo(fuso))
    except ValueError:
        raise ErroValidacao("Informe data e hora válidas.") from None


def _pagina(
    request: Request, db: Session, usuario: Usuario,
    contador_id: int | None, de_txt: str | None, ate_txt: str | None, agrupar: str | None,
    erro: str | None = None, novo: dict | None = None, status: int = 200,
):
    fuso = usuario.fuso_horario
    hoje = tempo.hoje_local(fuso, tempo.agora_utc())
    contadores = service.listar_contadores(db, usuario.id, ativos=None)
    contadores.sort(key=lambda c: (not c.ativo, c.posicao))
    agrupar = agrupar if agrupar in ("dia", "mes", "ano") else "dia"
    ate = _ler_data(ate_txt) or hoje
    de = _ler_data(de_txt) or ate - timedelta(days=DIAS_PADRAO - 1)
    erro_datas = None
    if de > ate:
        erro_datas = "A data inicial deve ser antes da final."

    contexto = {
        "contadores": contadores, "contador": None, "de": de, "ate": ate, "agrupar": agrupar,
        "agrupamentos": AGRUPAMENTOS, "erro": erro, "erro_datas": erro_datas, "grupos": [], "lancamentos": [],
        "novo": novo or {"quantidade": "1", "data": hoje.isoformat(), "hora": tempo.local(tempo.agora_utc(), fuso).strftime("%H:%M")},
        "rotulo_grupo": rotulo_grupo, "local": lambda instante: tempo.local(instante, fuso),
    }
    # Um id na URL sempre é verificado (404 se não for seu), mesmo sem contadores próprios.
    escolhido = service.obter_contador(db, usuario.id, contador_id) if contador_id is not None else None
    if contadores:
        contador = escolhido or contadores[0]
        contexto["contador"] = contador
        if not erro_datas:
            lista = lancamentos.listar_lancamentos(db, usuario.id, contador.id, de, ate, fuso)
            substitutos = {x.substitui_id: x for x in lista if x.substitui_id is not None}
            contexto.update(
                grupos=lancamentos.totais_agrupados(db, usuario.id, contador.id, de, ate, agrupar, fuso),
                lancamentos=lista,
                substitutos=substitutos,
            )
    return render(request, "historico/historico.html", contexto, status=status)


@router.get("")
def historico(
    request: Request,
    contador: int | None = None,
    de: str | None = None,
    ate: str | None = None,
    agrupar: str | None = None,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    return _pagina(request, db, usuario, contador, de, ate, agrupar)


def _url_historico(lanc: Lancamento) -> str:
    return f"/historico?contador={lanc.contador_id}"


@router.post("/lancamentos", dependencies=[Depends(exigir_csrf)])
def lancar_retroativo(
    request: Request,
    contador: int = Form(...),
    quantidade: str = Form(""),
    data: str = Form(""),
    hora: str = Form(""),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    alvo = service.obter_contador(db, usuario.id, contador)
    try:
        valor = ler_inteiro(quantidade, "Quantidade")
        lanc = lancamentos.registrar(
            db, usuario.id, alvo.id, valor, ocorrido_em=_momento_local(data, hora, usuario.fuso_horario)
        )
    except ErroValidacao as erro:
        return _pagina(request, db, usuario, alvo.id, None, None, None, erro=erro.mensagem,
                       novo={"quantidade": quantidade, "data": data, "hora": hora}, status=400)
    return RedirectResponse(_url_historico(lanc), status_code=303)


@router.post("/lancamentos/{lancamento_id}/cancelar", dependencies=[Depends(exigir_csrf)])
def cancelar(
    request: Request,
    lancamento_id: int,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    lanc = lancamentos.obter_lancamento(db, usuario.id, lancamento_id)
    try:
        lancamentos.cancelar(db, usuario.id, lanc.id)
    except ErroValidacao as erro:
        return _pagina(request, db, usuario, lanc.contador_id, None, None, None, erro=erro.mensagem, status=400)
    return RedirectResponse(_url_historico(lanc), status_code=303)


def _form_correcao(request: Request, db: Session, usuario: Usuario, lanc: Lancamento, valores: dict,
                   erro: str | None = None, status: int = 200):
    contador = service.obter_contador(db, usuario.id, lanc.contador_id)
    return render(request, "historico/corrigir.html",
                  {"lancamento": lanc, "contador": contador, "valores": valores, "erro": erro}, status=status)


@router.get("/lancamentos/{lancamento_id}/corrigir")
def form_corrigir(
    request: Request,
    lancamento_id: int,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    lanc = lancamentos.obter_lancamento(db, usuario.id, lancamento_id)
    momento = tempo.local(lanc.ocorrido_em, usuario.fuso_horario)
    return _form_correcao(request, db, usuario, lanc, {
        "quantidade": str(lanc.quantidade), "data": momento.date().isoformat(), "hora": momento.strftime("%H:%M"),
    })


@router.post("/lancamentos/{lancamento_id}/corrigir", dependencies=[Depends(exigir_csrf)])
def corrigir(
    request: Request,
    lancamento_id: int,
    quantidade: str = Form(""),
    data: str = Form(""),
    hora: str = Form(""),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    lanc = lancamentos.obter_lancamento(db, usuario.id, lancamento_id)
    try:
        valor = ler_inteiro(quantidade, "Quantidade")
        lancamentos.corrigir(db, usuario.id, lanc.id, valor, _momento_local(data, hora, usuario.fuso_horario))
    except ErroValidacao as erro:
        return _form_correcao(request, db, usuario, lanc,
                              {"quantidade": quantidade, "data": data, "hora": hora}, erro.mensagem, 400)
    return RedirectResponse(_url_historico(lanc), status_code=303)
