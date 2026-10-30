from dataclasses import dataclass
from datetime import date, time, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import tempo
from app.auth.deps import exigir_csrf, usuario_atual
from app.auth.models import Usuario
from app.db import get_db
from app.erros import ErroValidacao
from app.rotina import service
from app.rotina.layout import distribuir_faixas, faixa_horaria
from app.rotina.models import AtividadePlanejada
from app.rotina.service import CORES, DadosAtividade
from app.web import render

router = APIRouter(prefix="/rotina")

VISTAS = ("grade", "dia", "lista")
COOKIE_VISTA = "vista_rotina"
NOMES_CORES = {"verde": "Verde", "areia": "Areia", "lavanda": "Lavanda", "azul": "Azul", "rosa": "Rosa"}
_MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho",
          "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")


def _ler_data(texto: str | None, padrao: date) -> date:
    try:
        return date.fromisoformat(texto) if texto else padrao
    except ValueError:
        return padrao


def _ler_hora(texto: str) -> time:
    try:
        return time.fromisoformat(texto.strip())
    except ValueError:
        raise ErroValidacao("Informe horários válidos.") from None


def _hoje(usuario: Usuario) -> date:
    return tempo.hoje_local(usuario.fuso_horario, tempo.agora_utc())


def titulo_semana(segunda: date) -> str:
    domingo = segunda + timedelta(days=6)
    if segunda.month == domingo.month:
        return f"{segunda.day} a {domingo.day} de {_MESES[domingo.month - 1]}"
    return f"{segunda.day} de {_MESES[segunda.month - 1]} a {domingo.day} de {_MESES[domingo.month - 1]}"


@dataclass
class Dia:
    data: date
    nome: str
    curto: str
    atividades: list[AtividadePlanejada]


def _dias_da_semana(segunda: date, atividades: list[AtividadePlanejada]) -> list[Dia]:
    dias = []
    for i in range(7):
        d = segunda + timedelta(days=i)
        dias.append(Dia(d, tempo.NOMES_DIAS[i], tempo.NOMES_DIAS_CURTOS[i], [a for a in atividades if a.data == d]))
    return dias


@router.get("")
def semana(
    request: Request,
    semana: str | None = None,
    vista: str | None = None,
    dia: str | None = None,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    hoje = _hoje(usuario)
    segunda = tempo.inicio_semana(_ler_data(semana, hoje))
    vista_escolhida = vista if vista in VISTAS else None
    vista_atual = vista_escolhida or request.cookies.get(COOKIE_VISTA)
    if vista_atual not in VISTAS:
        vista_atual = "dia"
    dia_atual = _ler_data(dia, hoje if segunda <= hoje < segunda + timedelta(days=7) else segunda)
    if not segunda <= dia_atual < segunda + timedelta(days=7):
        dia_atual = segunda

    atividades = service.listar_semana(db, usuario.id, segunda)
    dias = _dias_da_semana(segunda, atividades)
    inicio_grade, fim_grade = faixa_horaria(atividades)
    resposta = render(request, "rotina/semana.html", {
        "segunda": segunda,
        "titulo_semana": titulo_semana(segunda),
        "anterior": segunda - timedelta(days=7),
        "proxima": segunda + timedelta(days=7),
        "hoje": hoje,
        "vista": vista_atual,
        "tem_cookie_vista": COOKIE_VISTA in request.cookies or vista_escolhida is not None,
        "dia_atual": dia_atual,
        "dias": dias,
        "atividades": atividades,
        "blocos_por_dia": {d.data: distribuir_faixas(d.atividades) for d in dias},
        "inicio_grade": inicio_grade,
        "fim_grade": fim_grade,
    })
    if vista_escolhida:
        resposta.set_cookie(COOKIE_VISTA, vista_escolhida, max_age=365 * 86400, samesite="lax")
    return resposta


def _contexto_form(**extra) -> dict:
    return {"cores": [(c, NOMES_CORES[c]) for c in CORES], "nomes_dias": tempo.NOMES_DIAS,
            "curtos_dias": tempo.NOMES_DIAS_CURTOS, **extra}


@router.get("/atividades/nova")
def nova_atividade(
    request: Request, semana: str | None = None, dia: str | None = None,
    usuario: Usuario = Depends(usuario_atual),
):
    hoje = _hoje(usuario)
    segunda = tempo.inicio_semana(_ler_data(semana, hoje))
    dia_marcado = _ler_data(dia, segunda)
    return render(request, "rotina/form.html", _contexto_form(
        atividade=None, segunda=segunda,
        valores={"titulo": "", "hora_inicio": "", "hora_fim": "", "descricao": "", "cor": "",
                 "dias": [(dia_marcado - segunda).days]},
    ))


def _dados_do_form(titulo: str, hora_inicio: str, hora_fim: str, descricao: str, cor: str) -> DadosAtividade:
    return DadosAtividade(titulo, _ler_hora(hora_inicio), _ler_hora(hora_fim), descricao, cor)


def _url_semana(d: date, dia: date | None = None) -> str:
    url = f"/rotina?semana={tempo.inicio_semana(d).isoformat()}"
    return f"{url}&dia={dia.isoformat()}" if dia else url


@router.post("/atividades", dependencies=[Depends(exigir_csrf)])
def criar_atividade(
    request: Request,
    semana: str = Form(""),
    titulo: str = Form(""),
    hora_inicio: str = Form(""),
    hora_fim: str = Form(""),
    descricao: str = Form(""),
    cor: str = Form(""),
    dias: list[str] = Form([]),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    segunda = tempo.inicio_semana(_ler_data(semana, _hoje(usuario)))
    dias_int = [int(d) for d in dias if d.isdigit()]
    try:
        criadas = service.criar_atividades(
            db, usuario.id, segunda, dias_int, _dados_do_form(titulo, hora_inicio, hora_fim, descricao, cor)
        )
    except ErroValidacao as erro:
        return render(request, "rotina/form.html", _contexto_form(
            atividade=None, segunda=segunda, erro=erro.mensagem,
            valores={"titulo": titulo, "hora_inicio": hora_inicio, "hora_fim": hora_fim,
                     "descricao": descricao, "cor": cor, "dias": dias_int},
        ), status=400)
    return RedirectResponse(_url_semana(segunda, criadas[0].data), status_code=303)


@router.get("/atividades/{atividade_id}/editar")
def editar_atividade(
    request: Request, atividade_id: int,
    usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db),
):
    a = service.obter_atividade(db, usuario.id, atividade_id)
    return render(request, "rotina/form.html", _contexto_form(
        atividade=a, segunda=tempo.inicio_semana(a.data),
        valores={"titulo": a.titulo, "hora_inicio": a.hora_inicio.strftime("%H:%M"),
                 "hora_fim": a.hora_fim.strftime("%H:%M"), "descricao": a.descricao or "",
                 "cor": a.cor or "", "escopo": "dia"},
    ))


@router.post("/atividades/{atividade_id}", dependencies=[Depends(exigir_csrf)])
def salvar_atividade(
    request: Request,
    atividade_id: int,
    titulo: str = Form(""),
    hora_inicio: str = Form(""),
    hora_fim: str = Form(""),
    descricao: str = Form(""),
    cor: str = Form(""),
    escopo: str = Form("dia"),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    a = service.obter_atividade(db, usuario.id, atividade_id)
    escopo = "grupo" if escopo == "grupo" else "dia"
    try:
        service.atualizar_atividade(
            db, usuario.id, atividade_id, _dados_do_form(titulo, hora_inicio, hora_fim, descricao, cor), escopo
        )
    except ErroValidacao as erro:
        return render(request, "rotina/form.html", _contexto_form(
            atividade=a, segunda=tempo.inicio_semana(a.data), erro=erro.mensagem,
            valores={"titulo": titulo, "hora_inicio": hora_inicio, "hora_fim": hora_fim,
                     "descricao": descricao, "cor": cor, "escopo": escopo},
        ), status=400)
    return RedirectResponse(_url_semana(a.data, a.data), status_code=303)


@router.post("/atividades/{atividade_id}/excluir", dependencies=[Depends(exigir_csrf)])
def excluir_atividade(
    atividade_id: int,
    escopo: str = Form("dia"),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    a = service.obter_atividade(db, usuario.id, atividade_id)
    data = a.data
    service.excluir_atividade(db, usuario.id, atividade_id, "grupo" if escopo == "grupo" else "dia")
    return RedirectResponse(_url_semana(data, data), status_code=303)


@router.post("/copiar-semana", dependencies=[Depends(exigir_csrf)])
def copiar_semana(
    request: Request,
    semana: str = Form(""),
    confirmar: str = Form(""),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    segunda = tempo.inicio_semana(_ler_data(semana, _hoje(usuario)))
    contexto = {"segunda": segunda, "titulo_semana": titulo_semana(segunda)}
    if confirmar != "sim" and service.listar_semana(db, usuario.id, segunda):
        return render(request, "rotina/copiar.html", contexto)
    try:
        service.copiar_semana_anterior(db, usuario.id, segunda)
    except ErroValidacao as erro:
        return render(request, "rotina/copiar.html", {**contexto, "erro": erro.mensagem}, status=400)
    return RedirectResponse(_url_semana(segunda), status_code=303)
