import uuid
from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

PASTA_APP = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=PASTA_APP / "templates")


def _registrar_globais() -> None:
    from app.contadores.apresentacao import ROTULO_PERIODO, texto_meta

    templates.env.globals.update(
        novo_token=lambda: str(uuid.uuid4()),  # token anti-duplicidade de cada envio
        texto_meta=texto_meta,
        ROTULO_PERIODO=ROTULO_PERIODO,
    )


_registrar_globais()


def render(request: Request, nome: str, contexto: dict | None = None, status: int = 200) -> HTMLResponse:
    sessao = getattr(request.state, "sessao", None)
    contexto = {
        "usuario": getattr(request.state, "usuario", None),
        "csrf_token": sessao.csrf_token if sessao else "",
        **(contexto or {}),
    }
    return templates.TemplateResponse(request, nome, contexto, status_code=status)


def eh_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"
