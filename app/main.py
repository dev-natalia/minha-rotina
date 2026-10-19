from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.erros import NaoEncontrado


def create_app() -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.exception_handler(NaoEncontrado)
    def nao_encontrado(request: Request, exc: NaoEncontrado) -> HTMLResponse:
        return HTMLResponse("<h1>Página não encontrada</h1>", status_code=404)

    @app.get("/healthz")
    def healthz(db: Session = Depends(get_db)) -> dict:
        db.execute(text("select 1"))
        return {"ok": True}

    return app


app = create_app()
