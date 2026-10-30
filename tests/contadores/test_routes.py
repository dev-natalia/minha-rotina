import re
import uuid
from datetime import datetime, timedelta
from datetime import timezone as tz

import pytest

from app import tempo
from app.contadores import lancamentos as L
from app.contadores import service
from app.contadores.apresentacao import texto_meta
from app.contadores.models import Contador
from app.contadores.service import DadosContador

SP = "America/Sao_Paulo"
AGORA = datetime(2026, 10, 19, 15, 0, tzinfo=tz.utc)


@pytest.fixture(autouse=True)
def relogio(monkeypatch):
    monkeypatch.setattr(tempo, "agora_utc", lambda: AGORA)


@pytest.fixture
def cigarros(db, usuario):
    return service.criar_contador(db, usuario.id, DadosContador("Cigarros", "unidade"))


def total(db, usuario, contador, periodo="dia"):
    return L.totais_periodo(db, usuario.id, periodo, SP, AGORA)[contador.id]


def mais(post, cliente, contador, token=None, htmx=True, **extra):
    dados = {"token": token or str(uuid.uuid4()), "periodo": "dia", "voltar": "/contadores", **extra}
    return post(cliente, f"/contadores/{contador.id}/mais", dados, htmx=htmx)


def test_contadores_exige_login(cliente):
    assert cliente.get("/contadores", follow_redirects=False).status_code == 303


def test_lista_vazia_convida_a_criar(cliente_logado):
    html = cliente_logado.get("/contadores").text
    assert "Você ainda não tem contadores." in html
    assert "Criar contador" in html


def test_criar_contador_pela_tela(cliente_logado, post, db, usuario):
    r = post(cliente_logado, "/contadores", {
        "nome": "Água", "unidade": "copo", "passo": "1",
        "meta_valor": "8", "meta_periodo": "dia", "meta_sentido": "minimo",
    })
    assert r.status_code == 303
    [c] = service.listar_contadores(db, usuario.id)
    assert (c.nome, c.meta_valor, c.meta_sentido) == ("Água", 8, "minimo")
    assert "Água" in cliente_logado.get("/contadores").text


def test_criar_contador_com_valor_inicial(cliente_logado, post, db, usuario):
    post(cliente_logado, "/contadores", {"nome": "Treinos", "unidade": "sessão", "passo": "1",
                                         "valor_inicial": "40", "valor_inicial_data": "2026-01-01"})
    [c] = service.listar_contadores(db, usuario.id)
    assert L.totais_periodo(db, usuario.id, "ano", SP, AGORA)[c.id] == 40


def test_criar_contador_invalido_mostra_erro(cliente_logado, post, db, usuario):
    r = post(cliente_logado, "/contadores", {"nome": "Água", "unidade": "", "passo": "1"})
    assert r.status_code == 400
    assert "Informe a unidade." in r.text
    assert 'value="Água"' in r.text
    assert service.listar_contadores(db, usuario.id, ativos=None) == []


def test_mais_registra_e_devolve_card(cliente_logado, post, db, usuario, cigarros):
    r = mais(post, cliente_logado, cigarros)
    assert r.status_code == 200
    assert re.search(r'class="contador-valor"[^>]*>\s*1\s*<', r.text)
    assert 'id="anuncio"' in r.text and "Cigarros: 1 hoje" in r.text
    assert total(db, usuario, cigarros) == 1


def test_mais_usa_o_passo(cliente_logado, post, db, usuario):
    estudo = service.criar_contador(db, usuario.id, DadosContador("Estudo", "minuto", passo=15))
    mais(post, cliente_logado, estudo)
    assert total(db, usuario, estudo) == 15


def test_mais_com_mesmo_token_duas_vezes(cliente_logado, post, db, usuario, cigarros):
    token = str(uuid.uuid4())
    mais(post, cliente_logado, cigarros, token=token)
    mais(post, cliente_logado, cigarros, token=token)
    assert total(db, usuario, cigarros) == 1


def test_card_traz_tokens_novos(cliente_logado, post, cigarros):
    token = str(uuid.uuid4())
    r = mais(post, cliente_logado, cigarros, token=token)
    assert token not in r.text
    assert re.search(r'name="token" value="[0-9a-f-]{36}"', r.text)


def test_quantidade_registra(cliente_logado, post, db, usuario, cigarros):
    r = post(cliente_logado, f"/contadores/{cigarros.id}/quantidade",
             {"quantidade": "30", "token": str(uuid.uuid4()), "periodo": "dia", "voltar": "/contadores"}, htmx=True)
    assert r.status_code == 200
    assert total(db, usuario, cigarros) == 30


@pytest.mark.parametrize("valor", ["0", "-3", "abc", "99999999999", ""])
def test_quantidade_invalida_nao_registra(cliente_logado, post, db, usuario, cigarros, valor):
    r = post(cliente_logado, f"/contadores/{cigarros.id}/quantidade",
             {"quantidade": valor, "token": str(uuid.uuid4()), "periodo": "dia", "voltar": "/contadores"}, htmx=True)
    assert r.status_code == 400
    assert "Quantidade: informe um número inteiro entre 1 e 1000000." in r.text
    assert 'role="alert"' in r.text
    assert total(db, usuario, cigarros) == 0


def test_menos_desfaz(cliente_logado, post, db, usuario, cigarros):
    L.registrar(db, usuario.id, cigarros.id, 1)
    L.registrar(db, usuario.id, cigarros.id, 1)
    r = post(cliente_logado, f"/contadores/{cigarros.id}/menos", {"periodo": "dia", "voltar": "/contadores"}, htmx=True)
    assert r.status_code == 200
    assert "Cigarros: 1 hoje" in r.text
    assert total(db, usuario, cigarros) == 1


def test_menos_desabilitado_sem_lancamentos(cliente_logado, cigarros):
    html = cliente_logado.get("/contadores").text
    assert re.search(r'<button[^>]*class="botao-menos"[^>]*disabled', html)


def test_menos_sem_lancamentos_nao_quebra(cliente_logado, post, cigarros):
    r = post(cliente_logado, f"/contadores/{cigarros.id}/menos", {"periodo": "dia", "voltar": "/contadores"}, htmx=True)
    assert r.status_code == 200


def test_periodo_mes_soma_o_mes_e_fica_no_cookie(cliente_logado, db, usuario, cigarros):
    L.registrar(db, usuario.id, cigarros.id, 2, ocorrido_em=AGORA - timedelta(days=5))
    L.registrar(db, usuario.id, cigarros.id, 1)
    r = cliente_logado.get("/contadores?periodo=mes")
    assert re.search(r'class="contador-valor"[^>]*>\s*3\s*<', r.text)
    assert "periodo_contadores=mes" in r.headers.get("set-cookie", "")
    html = cliente_logado.get("/contadores").text
    assert re.search(r'class="contador-valor"[^>]*>\s*3\s*<', html)


def test_periodo_invalido_usa_dia(cliente_logado, db, usuario, cigarros):
    L.registrar(db, usuario.id, cigarros.id, 2, ocorrido_em=AGORA - timedelta(days=5))
    html = cliente_logado.get("/contadores?periodo=semana").text
    assert re.search(r'class="contador-valor"[^>]*>\s*0\s*<', html)


def test_texto_meta():
    maximo = Contador(nome="Cigarros", unidade="unidade", passo=1, meta_valor=5, meta_periodo="dia", meta_sentido="maximo")
    minimo = Contador(nome="Água", unidade="copo", passo=1, meta_valor=8, meta_periodo="dia", meta_sentido="minimo")
    sem_meta = Contador(nome="X", unidade="u", passo=1)
    assert texto_meta(maximo, 7, "dia") == "7 de no máximo 5 · acima da meta"
    assert texto_meta(maximo, 5, "dia") == "5 de no máximo 5"
    assert texto_meta(minimo, 8, "dia") == "8 de 8 · meta atingida"
    assert texto_meta(minimo, 4, "dia") == "4 de 8"
    assert texto_meta(maximo, 7, "mes") is None
    assert texto_meta(sem_meta, 1, "dia") is None


def test_meta_aparece_no_card(cliente_logado, post, db, usuario):
    c = service.criar_contador(db, usuario.id, DadosContador("Cigarros", "unidade", meta_valor=5, meta_periodo="dia", meta_sentido="maximo"))
    for _ in range(7):
        L.registrar(db, usuario.id, c.id, 1)
    assert "7 de no máximo 5 · acima da meta" in cliente_logado.get("/contadores").text


def test_mais_em_contador_de_outro_usuario_404(cliente_logado, post, db, outro_usuario):
    dela = service.criar_contador(db, outro_usuario.id, DadosContador("Dela", "u"))
    assert mais(post, cliente_logado, dela).status_code == 404
    assert post(cliente_logado, f"/contadores/{dela.id}/menos", {"periodo": "dia"}, htmx=True).status_code == 404
    assert cliente_logado.get(f"/contadores/{dela.id}/editar").status_code == 404
    assert post(cliente_logado, f"/contadores/{dela.id}/ativo", {"ativo": "nao"}).status_code == 404
    assert L.totais_periodo(db, outro_usuario.id, "dia", SP, AGORA)[dela.id] == 0


def test_desativar_some_da_tela(cliente_logado, post, db, usuario, cigarros):
    assert post(cliente_logado, f"/contadores/{cigarros.id}/ativo", {"ativo": "nao"}).status_code == 303
    assert "Cigarros" not in cliente_logado.get("/contadores").text
    gerenciar = cliente_logado.get("/contadores/gerenciar").text
    assert "Cigarros" in gerenciar and "Ativar" in gerenciar


def test_editar_contador(cliente_logado, post, db, cigarros):
    assert 'value="Cigarros"' in cliente_logado.get(f"/contadores/{cigarros.id}/editar").text
    r = post(cliente_logado, f"/contadores/{cigarros.id}", {"nome": "Cigarros", "unidade": "unidade", "passo": "2"})
    assert r.status_code == 303
    db.refresh(cigarros)
    assert cigarros.passo == 2


def test_sem_js_redireciona_para_voltar(cliente_logado, post, cigarros):
    r = mais(post, cliente_logado, cigarros, htmx=False, voltar="/")
    assert r.status_code == 303
    assert r.headers["location"] == "/"


def test_voltar_externo_e_ignorado(cliente_logado, post, cigarros):
    r = mais(post, cliente_logado, cigarros, htmx=False, voltar="https://mal.example")
    assert r.headers["location"] == "/contadores"
    r = mais(post, cliente_logado, cigarros, htmx=False, voltar="//mal.example")
    assert r.headers["location"] == "/contadores"


def test_post_sem_csrf_403(cliente_logado, cigarros):
    r = cliente_logado.post(f"/contadores/{cigarros.id}/mais", data={"token": str(uuid.uuid4())}, follow_redirects=False)
    assert r.status_code == 403
