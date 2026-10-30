from datetime import date, datetime
from datetime import timezone as tz

import pytest

from app import tempo
from app.contadores import lancamentos as L
from app.contadores import service
from app.contadores.service import DadosContador

SP = "America/Sao_Paulo"
AGORA = datetime(2026, 10, 19, 15, 0, tzinfo=tz.utc)  # 12:00 de 19/10 em SP
SEM_REGISTROS = '<abbr title="sem registros">—</abbr>'


def utc(*args):
    return datetime(*args, tzinfo=tz.utc)


@pytest.fixture(autouse=True)
def relogio(monkeypatch):
    monkeypatch.setattr(tempo, "agora_utc", lambda: AGORA)


@pytest.fixture
def cigarros(db, usuario):
    return service.criar_contador(db, usuario.id, DadosContador("Cigarros", "unidade"))


def historico(cliente, contador, **params):
    query = "&".join(f"{k}={v}" for k, v in {"contador": contador.id, **params}.items())
    return cliente.get(f"/historico?{query}")


def test_historico_exige_login(cliente):
    assert cliente.get("/historico", follow_redirects=False).status_code == 303


def test_historico_sem_contadores_convida(cliente_logado):
    html = cliente_logado.get("/historico").text
    assert "Você ainda não tem contadores." in html


def test_historico_usa_primeiro_contador_e_ultimos_30_dias(cliente_logado, cigarros):
    html = cliente_logado.get("/historico").text
    assert 'value="2026-09-20"' in html and 'value="2026-10-19"' in html
    assert f'<option value="{cigarros.id}" selected' in html


def test_historico_mostra_traco_para_dia_sem_registros(cliente_logado, db, usuario, cigarros):
    L.registrar(db, usuario.id, cigarros.id, 3, ocorrido_em=utc(2026, 10, 19, 14))
    html = historico(cliente_logado, cigarros, de="2026-10-17", ate="2026-10-19").text
    assert html.count(SEM_REGISTROS) == 2
    assert "19/10" in html and "17/10" in html


def test_historico_mostra_cancelado(cliente_logado, db, usuario, cigarros):
    lanc = L.registrar(db, usuario.id, cigarros.id, 1)
    L.cancelar(db, usuario.id, lanc.id)
    html = historico(cliente_logado, cigarros).text
    assert "<del" in html and "cancelado" in html


def test_historico_mostra_ajuste(cliente_logado, db, usuario):
    c = service.criar_contador(db, usuario.id, DadosContador("Treinos", "sessão"), valor_inicial=40)
    assert "ajuste" in historico(cliente_logado, c).text


def test_historico_agrupado_por_mes(cliente_logado, db, usuario, cigarros):
    L.registrar(db, usuario.id, cigarros.id, 2, ocorrido_em=utc(2026, 9, 10, 15))
    html = historico(cliente_logado, cigarros, de="2026-08-01", ate="2026-10-19", agrupar="mes").text
    assert "setembro de 2026" in html and "outubro de 2026" in html


def test_lancamento_retroativo(cliente_logado, post, db, usuario, cigarros):
    r = post(cliente_logado, "/historico/lancamentos",
             {"contador": str(cigarros.id), "quantidade": "2", "data": "2026-10-18", "hora": "15:00"})
    assert r.status_code == 303
    [lanc] = L.listar_lancamentos(db, usuario.id, cigarros.id, date(2026, 10, 18), date(2026, 10, 18), SP)
    assert lanc.ocorrido_em == utc(2026, 10, 18, 18, 0)  # 15:00 em SP
    html = historico(cliente_logado, cigarros).text
    assert "15:00" in html


def test_retroativo_no_futuro_erro(cliente_logado, post, db, usuario, cigarros):
    r = post(cliente_logado, "/historico/lancamentos",
             {"contador": str(cigarros.id), "quantidade": "1", "data": "2026-10-20", "hora": "10:00"})
    assert r.status_code == 400
    assert "A data não pode estar no futuro." in r.text
    assert L.listar_lancamentos(db, usuario.id, cigarros.id, date(2026, 10, 1), date(2026, 10, 31), SP) == []


def test_retroativo_quantidade_invalida(cliente_logado, post, cigarros):
    r = post(cliente_logado, "/historico/lancamentos",
             {"contador": str(cigarros.id), "quantidade": "0", "data": "2026-10-18", "hora": "10:00"})
    assert r.status_code == 400
    assert "Quantidade: informe um número inteiro entre 1 e 1000000." in r.text


def test_retroativo_data_invalida(cliente_logado, post, cigarros):
    r = post(cliente_logado, "/historico/lancamentos",
             {"contador": str(cigarros.id), "quantidade": "1", "data": "ontem", "hora": "10:00"})
    assert r.status_code == 400
    assert "Informe data e hora válidas." in r.text


def test_cancelar_pela_tela(cliente_logado, post, db, usuario, cigarros):
    lanc = L.registrar(db, usuario.id, cigarros.id, 1)
    r = post(cliente_logado, f"/historico/lancamentos/{lanc.id}/cancelar")
    assert r.status_code == 303
    db.refresh(lanc)
    assert lanc.cancelado_em is not None


def test_corrigir_pela_tela(cliente_logado, post, db, usuario, cigarros):
    lanc = L.registrar(db, usuario.id, cigarros.id, 1, ocorrido_em=utc(2026, 10, 19, 13))
    form = cliente_logado.get(f"/historico/lancamentos/{lanc.id}/corrigir").text
    assert 'value="10:00"' in form and 'value="2026-10-19"' in form
    r = post(cliente_logado, f"/historico/lancamentos/{lanc.id}/corrigir",
             {"quantidade": "4", "data": "2026-10-19", "hora": "09:30"})
    assert r.status_code == 303
    assert L.totais_periodo(db, usuario.id, "dia", SP, AGORA)[cigarros.id] == 4
    html = historico(cliente_logado, cigarros).text
    assert "corrigido" in html


def test_corrigir_com_erro_mostra_form(cliente_logado, post, db, usuario, cigarros):
    lanc = L.registrar(db, usuario.id, cigarros.id, 1)
    r = post(cliente_logado, f"/historico/lancamentos/{lanc.id}/corrigir",
             {"quantidade": "abc", "data": "2026-10-19", "hora": "09:30"})
    assert r.status_code == 400
    assert 'value="abc"' in r.text
    db.refresh(lanc)
    assert lanc.cancelado_em is None


def test_cancelar_lancamento_de_outro_usuario_404(cliente_logado, post, db, outro_usuario):
    dela = service.criar_contador(db, outro_usuario.id, DadosContador("Dela", "u"))
    lanc = L.registrar(db, outro_usuario.id, dela.id, 1)
    assert post(cliente_logado, f"/historico/lancamentos/{lanc.id}/cancelar").status_code == 404
    assert cliente_logado.get(f"/historico/lancamentos/{lanc.id}/corrigir").status_code == 404
    r = post(cliente_logado, f"/historico/lancamentos/{lanc.id}/corrigir",
             {"quantidade": "9", "data": "2026-10-19", "hora": "09:30"})
    assert r.status_code == 404
    assert cliente_logado.get(f"/historico?contador={dela.id}").status_code == 404
    r = post(cliente_logado, "/historico/lancamentos",
             {"contador": str(dela.id), "quantidade": "1", "data": "2026-10-18", "hora": "10:00"})
    assert r.status_code == 404
    db.refresh(lanc)
    assert lanc.cancelado_em is None


def test_datas_invertidas_mostra_erro(cliente_logado, cigarros):
    html = historico(cliente_logado, cigarros, de="2026-10-19", ate="2026-10-01").text
    assert "A data inicial deve ser antes da final." in html


def test_contador_inativo_aparece_no_seletor(cliente_logado, db, usuario, cigarros):
    service.definir_ativo(db, usuario.id, cigarros.id, False)
    html = cliente_logado.get("/historico").text
    assert "Cigarros (inativo)" in html


def test_post_sem_csrf_403(cliente_logado, cigarros):
    r = cliente_logado.post("/historico/lancamentos", data={"contador": str(cigarros.id)}, follow_redirects=False)
    assert r.status_code == 403
