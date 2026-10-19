from fastapi import APIRouter, Depends, Request

from app.auth.deps import usuario_atual
from app.web import render

router = APIRouter(dependencies=[Depends(usuario_atual)])


@router.get("/")
def painel(request: Request):
    # Provisório: o painel de verdade chega na tarefa 12.
    return render(request, "painel/painel.html")
