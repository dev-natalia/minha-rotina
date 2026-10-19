import re
from datetime import date, datetime, time
from datetime import timezone as tz

import pytest

from app import tempo
from app.contadores import lancamentos as L
from app.contadores import service as contadores
from app.contadores.service import DadosContador
from app.painel.routes import estado_atividade, saudacao
from app.rotina import service as rotina
from app.rotina.models import AtividadePlanejada
from app.rotina.service import DadosAtividade

AGORA = datetime(2026, 10, 19, 13, 0, tzinfo=tz.utc)  # 10:00 de segunda, 19/10, em SP


@pytest.fixture(autouse=True)
def relogio(monkeypatch):
    monkeypatch.setattr(tempo, "agora_utc", lambda: AGORA)


def test_saudacao():
    assert saudacao(5) == "Bom dia"
    assert saudacao(11) == "Bom dia"
    assert saudacao(12) == "Boa tarde"
    assert saudacao(17) == "Boa tarde"
    assert saudacao(18) == "Boa noite"
    assert saudacao(0) == "Boa noite"


def test_estado_atividade():
    a = AtividadePlanejada(titulo="T", data=date(2026, 10, 19), hora_inicio=time(8), hora_fim=time(12))
    assert estado_atividade(a, datetime(2026, 10, 19, 10, 0)) == "agora"
    assert estado_atividade(a, datetime(2026, 10, 19, 8, 0)) == "agora"
    assert estado_atividade(a, datetime(2026, 10, 19, 12, 0)) == "passada"
    assert estado_atividade(a, datetime(2026, 10, 19, 7, 59)) == "futura"


def test_painel_exige_login(cliente):
    r = cliente.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_painel_mostra_rotina_de_hoje_e_contadores(cliente_logado, db, usuario):
    rotina.criar_atividades(db, usuario.id, date(2026, 10, 19), [0], DadosAtividade("Trabalho", time(8), time(12)))
    rotina.criar_atividades(db, usuario.id, date(2026, 10, 19), [0], DadosAtividade("Café", time(7), time(7, 30)))
    rotina.criar_atividades(db, usuario.id, date(2026, 10, 19), [0], DadosAtividade("Estudos", time(19), time(21)))
    rotina.criar_atividades(db, usuario.id, date(2026, 10, 19), [1], DadosAtividade("Dentista", time(9), time(10)))
    c = contadores.criar_contador(db, usuario.id, DadosContador("Cigarros", "unidade"))
    L.registrar(db, usuario.id, c.id, 2)
    L.registrar(db, usuario.id, c.id, 5, ocorrido_em=datetime(2026, 10, 18, 15, tzinfo=tz.utc))  # ontem

    html = cliente_logado.get("/").text
    assert "Segunda-feira, 19 de outubro" in html
    assert "Bom dia, Ana" in html
    assert "Trabalho" in html and "Estudos" in html
    assert "Dentista" not in html
    assert re.search(r'class="[^"]*passada[^"]*"[^>]*>.*?Café', html, re.S)
    assert re.search(r"Trabalho.*?agora", html, re.S)
    assert "Cigarros" in html
    assert re.search(r'class="contador-valor"[^>]*>\s*2\s*<', html)


def test_painel_contadores_voltam_para_o_painel(cliente_logado, db, usuario):
    contadores.criar_contador(db, usuario.id, DadosContador("Água", "copo"))
    html = cliente_logado.get("/").text
    assert 'name="voltar" value="/"' in html
    assert 'name="periodo" value="dia"' in html


def test_painel_ignora_contador_inativo(cliente_logado, db, usuario):
    c = contadores.criar_contador(db, usuario.id, DadosContador("Antigo", "u"))
    contadores.definir_ativo(db, usuario.id, c.id, False)
    assert "Antigo" not in cliente_logado.get("/").text


def test_painel_sem_dados_mostra_convites(cliente_logado):
    html = cliente_logado.get("/").text
    assert "Nada planejado para hoje." in html
    assert 'href="/rotina"' in html
    assert 'href="/contadores/novo"' in html


def test_painel_nao_mostra_dados_de_outro_usuario(cliente_logado, db, outro_usuario):
    rotina.criar_atividades(db, outro_usuario.id, date(2026, 10, 19), [0], DadosAtividade("Segredo", time(8), time(9)))
    contadores.criar_contador(db, outro_usuario.id, DadosContador("Privado", "u"))
    html = cliente_logado.get("/").text
    assert "Segredo" not in html and "Privado" not in html
