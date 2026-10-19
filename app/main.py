from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.deps import NaoAutenticado
from app.db import get_db
from app.erros import NaoEncontrado
from app.web import PASTA_APP, eh_htmx, render


def create_app() -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=PASTA_APP / "static"), name="static")

    @app.exception_handler(NaoAutenticado)
    def nao_autenticado(request: Request, exc: NaoAutenticado) -> Response:
        if eh_htmx(request):
            # Sem isso o HTMX colocaria a tela de login dentro de um card.
            return Response(status_code=200, headers={"HX-Redirect": "/login"})
        return Response(status_code=303, headers={"Location": "/login"})

    @app.exception_handler(NaoEncontrado)
    def nao_encontrado(request: Request, exc: NaoEncontrado) -> HTMLResponse:
        return render(request, "erro.html", {"titulo": "Página não encontrada"}, status=404)

    @app.exception_handler(HTTPException)
    def erro_http(request: Request, exc: HTTPException) -> HTMLResponse:
        mensagem = exc.detail if isinstance(exc.detail, str) else "Algo deu errado."
        if exc.status_code == 404:
            mensagem = "Página não encontrada"
        return render(request, "erro.html", {"titulo": mensagem}, status=exc.status_code)

    @app.exception_handler(RequestValidationError)
    def dados_invalidos(request: Request, exc: RequestValidationError) -> HTMLResponse:
        return render(request, "erro.html", {"titulo": "Dados inválidos."}, status=400)

    @app.get("/healthz")
    def healthz(db: Session = Depends(get_db)) -> dict:
        db.execute(text("select 1"))
        return {"ok": True}

    from app.auth.routes import router as auth_router
    from app.contadores.routes import router as contadores_router
    from app.painel.routes import router as painel_router
    from app.pwa.routes import router as pwa_router
    from app.rotina.routes import router as rotina_router

    app.include_router(auth_router)
    app.include_router(painel_router)
    app.include_router(pwa_router)
    app.include_router(rotina_router)
    app.include_router(contadores_router)
    return app


app = create_app()
