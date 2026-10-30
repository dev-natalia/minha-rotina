import uuid
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import tempo
from app.auth.deps import exigir_csrf, usuario_atual
from app.auth.models import Usuario
from app.contadores import lancamentos, service
from app.contadores.apresentacao import NOME_PERIODO, descricao_meta
from app.contadores.models import Contador
from app.contadores.service import DadosContador, ler_inteiro
from app.db import get_db
from app.erros import ErroValidacao
from app.web import eh_htmx, render

router = APIRouter(prefix="/contadores")

PERIODOS = ("dia", "mes", "ano")
COOKIE_PERIODO = "periodo_contadores"

def _periodo(valor: str | None) -> str:
    return valor if valor in PERIODOS else "dia"


def _voltar(valor: str | None) -> str:
    if valor == "/" or (valor or "").startswith("/contadores"):
        return valor
    return "/contadores"


def contexto_cartoes(db: Session, usuario: Usuario, periodo: str, contadores: list[Contador]) -> dict:
    """Totais e estado do botão "−" para uma lista de cartões (também usado pelo painel)."""
    agora = tempo.agora_utc()
    return {
        "totais": lancamentos.totais_periodo(db, usuario.id, periodo, usuario.fuso_horario, agora),
        "desfazer": lancamentos.pode_desfazer(db, usuario.id, periodo, usuario.fuso_horario, agora),
    }


@router.get("")
def lista(
    request: Request,
    periodo: str | None = None,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    escolhido = periodo if periodo in PERIODOS else None
    atual = _periodo(escolhido or request.cookies.get(COOKIE_PERIODO))
    contadores = service.listar_contadores(db, usuario.id)
    resposta = render(request, "contadores/lista.html", {
        "periodo": atual,
        "periodos": [(p, NOME_PERIODO[p]) for p in PERIODOS],
        "contadores": contadores,
        "voltar": "/contadores",
        **contexto_cartoes(db, usuario, atual, contadores),
    })
    if escolhido:
        resposta.set_cookie(COOKIE_PERIODO, escolhido, max_age=365 * 86400, samesite="lax")
    return resposta


def _responder_cartao(
    request: Request, db: Session, usuario: Usuario, contador: Contador, periodo: str, voltar: str,
    erro: str | None = None,
):
    if not eh_htmx(request):
        if erro:
            return render(request, "erro.html", {"titulo": erro}, status=400)
        return RedirectResponse(voltar, status_code=303)
    ctx = contexto_cartoes(db, usuario, periodo, [contador])
    return render(request, "contadores/_resposta_cartao.html", {
        "contador": contador,
        "total": ctx["totais"].get(contador.id, 0),
        "pode_desfazer": contador.id in ctx["desfazer"],
        "periodo": periodo,
        "voltar": voltar,
        "erro": erro,
    }, status=400 if erro else 200)


def _ler_token(valor: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(valor)
    except ValueError:
        return None


@router.post("/{contador_id}/mais", dependencies=[Depends(exigir_csrf)])
def mais(
    request: Request,
    contador_id: int,
    token: str = Form(""),
    periodo: str = Form("dia"),
    voltar: str = Form("/contadores"),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    contador = service.obter_contador(db, usuario.id, contador_id)
    erro = None
    try:
        lancamentos.registrar(db, usuario.id, contador.id, contador.passo, token=_ler_token(token))
    except ErroValidacao as e:
        erro = e.mensagem
    return _responder_cartao(request, db, usuario, contador, _periodo(periodo), _voltar(voltar), erro)


@router.post("/{contador_id}/quantidade", dependencies=[Depends(exigir_csrf)])
def quantidade(
    request: Request,
    contador_id: int,
    quantidade: str = Form(""),
    token: str = Form(""),
    periodo: str = Form("dia"),
    voltar: str = Form("/contadores"),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    contador = service.obter_contador(db, usuario.id, contador_id)
    erro = None
    try:
        valor = ler_inteiro(quantidade, "Quantidade")
        lancamentos.registrar(db, usuario.id, contador.id, valor, token=_ler_token(token))
    except ErroValidacao as e:
        erro = e.mensagem
    return _responder_cartao(request, db, usuario, contador, _periodo(periodo), _voltar(voltar), erro)


@router.post("/{contador_id}/menos", dependencies=[Depends(exigir_csrf)])
def menos(
    request: Request,
    contador_id: int,
    periodo: str = Form("dia"),
    voltar: str = Form("/contadores"),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    contador = service.obter_contador(db, usuario.id, contador_id)
    periodo = _periodo(periodo)
    lancamentos.desfazer_ultimo(db, usuario.id, contador.id, periodo, usuario.fuso_horario, tempo.agora_utc())
    return _responder_cartao(request, db, usuario, contador, periodo, _voltar(voltar))


# --- Gerenciar contadores ---------------------------------------------------

@router.get("/gerenciar")
def gerenciar(request: Request, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    todos = service.listar_contadores(db, usuario.id, ativos=None)
    return render(request, "contadores/gerenciar.html", {
        "ativos": [c for c in todos if c.ativo],
        "inativos": [c for c in todos if not c.ativo],
        "descricao_meta": descricao_meta,
    })


def _valores_vazios() -> dict:
    return {"nome": "", "unidade": "", "passo": "1", "meta_valor": "", "meta_periodo": "dia",
            "meta_sentido": "maximo", "valor_inicial": "", "valor_inicial_data": ""}


@router.get("/novo")
def novo(request: Request, usuario: Usuario = Depends(usuario_atual)):
    valores = _valores_vazios()
    valores["valor_inicial_data"] = tempo.hoje_local(usuario.fuso_horario, tempo.agora_utc()).isoformat()
    return render(request, "contadores/form.html", {"contador": None, "valores": valores})


def _dados(valores: dict) -> DadosContador:
    passo = ler_inteiro(valores["passo"], "Passo")
    meta_valor = ler_inteiro(valores["meta_valor"], "Meta") if valores["meta_valor"].strip() else None
    return DadosContador(
        nome=valores["nome"], unidade=valores["unidade"], passo=passo, meta_valor=meta_valor,
        meta_periodo=valores["meta_periodo"] if meta_valor else None,
        meta_sentido=valores["meta_sentido"] if meta_valor else None,
    )


def _momento_valor_inicial(texto: str, usuario: Usuario) -> datetime:
    """Meio-dia local da data informada (ou agora, se vazia)."""
    if not texto.strip():
        return tempo.agora_utc()
    try:
        dia = date.fromisoformat(texto.strip())
    except ValueError:
        raise ErroValidacao("Informe uma data válida para o valor inicial.") from None
    return datetime.combine(dia, time(12), tzinfo=ZoneInfo(usuario.fuso_horario))


@router.post("", dependencies=[Depends(exigir_csrf)])
def criar(
    request: Request,
    nome: str = Form(""),
    unidade: str = Form(""),
    passo: str = Form("1"),
    meta_valor: str = Form(""),
    meta_periodo: str = Form("dia"),
    meta_sentido: str = Form("maximo"),
    valor_inicial: str = Form(""),
    valor_inicial_data: str = Form(""),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    valores = {"nome": nome, "unidade": unidade, "passo": passo, "meta_valor": meta_valor,
               "meta_periodo": meta_periodo, "meta_sentido": meta_sentido,
               "valor_inicial": valor_inicial, "valor_inicial_data": valor_inicial_data}
    try:
        inicial = ler_inteiro(valor_inicial, "Valor inicial", minimo=0) if valor_inicial.strip() else None
        service.criar_contador(
            db, usuario.id, _dados(valores),
            valor_inicial=inicial or None,
            valor_inicial_em=_momento_valor_inicial(valor_inicial_data, usuario) if inicial else None,
        )
    except ErroValidacao as erro:
        return render(request, "contadores/form.html",
                      {"contador": None, "valores": valores, "erro": erro.mensagem}, status=400)
    return RedirectResponse("/contadores", status_code=303)


@router.get("/{contador_id}/editar")
def editar(
    request: Request, contador_id: int,
    usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db),
):
    c = service.obter_contador(db, usuario.id, contador_id)
    valores = {**_valores_vazios(), "nome": c.nome, "unidade": c.unidade, "passo": str(c.passo),
               "meta_valor": str(c.meta_valor or ""), "meta_periodo": c.meta_periodo or "dia",
               "meta_sentido": c.meta_sentido or "maximo"}
    return render(request, "contadores/form.html", {"contador": c, "valores": valores})


@router.post("/{contador_id}", dependencies=[Depends(exigir_csrf)])
def salvar(
    request: Request,
    contador_id: int,
    nome: str = Form(""),
    unidade: str = Form(""),
    passo: str = Form("1"),
    meta_valor: str = Form(""),
    meta_periodo: str = Form("dia"),
    meta_sentido: str = Form("maximo"),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    c = service.obter_contador(db, usuario.id, contador_id)
    valores = {**_valores_vazios(), "nome": nome, "unidade": unidade, "passo": passo, "meta_valor": meta_valor,
               "meta_periodo": meta_periodo, "meta_sentido": meta_sentido}
    try:
        service.atualizar_contador(db, usuario.id, c.id, _dados(valores))
    except ErroValidacao as erro:
        return render(request, "contadores/form.html",
                      {"contador": c, "valores": valores, "erro": erro.mensagem}, status=400)
    return RedirectResponse("/contadores/gerenciar", status_code=303)


@router.post("/{contador_id}/ativo", dependencies=[Depends(exigir_csrf)])
def ativo(
    contador_id: int,
    ativo: str = Form("sim"),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    service.definir_ativo(db, usuario.id, contador_id, ativo == "sim")
    return RedirectResponse("/contadores/gerenciar", status_code=303)
