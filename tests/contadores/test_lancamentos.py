import uuid
from datetime import date, datetime, timedelta
from datetime import timezone as tz

import pytest

from app import tempo
from app.contadores import lancamentos as L
from app.contadores import service
from app.contadores.lancamentos import TotalGrupo
from app.contadores.service import DadosContador
from app.erros import ErroValidacao, NaoEncontrado

SP = "America/Sao_Paulo"
AGORA = datetime(2026, 10, 19, 15, 0, tzinfo=tz.utc)  # 12:00 de 19/10 em SP


def utc(*args):
    return datetime(*args, tzinfo=tz.utc)


@pytest.fixture(autouse=True)
def relogio(monkeypatch):
    monkeypatch.setattr(tempo, "agora_utc", lambda: AGORA)


@pytest.fixture
def contador(db, usuario):
    return service.criar_contador(db, usuario.id, DadosContador("Cigarros", "unidade"))


def total(db, usuario, contador, periodo="dia", agora=AGORA):
    return L.totais_periodo(db, usuario.id, periodo, SP, agora)[contador.id]


def test_registrar_soma_no_total_do_dia(db, usuario, contador):
    L.registrar(db, usuario.id, contador.id, 1)
    L.registrar(db, usuario.id, contador.id, 1)
    L.registrar(db, usuario.id, contador.id, 30)
    assert total(db, usuario, contador) == 32


def test_registrar_usa_agora_por_padrao(db, usuario, contador):
    lanc = L.registrar(db, usuario.id, contador.id, 1)
    assert lanc.ocorrido_em == AGORA
    assert lanc.tipo == "normal"


def test_registrar_mesmo_token_nao_duplica(db, usuario, contador):
    token = uuid.uuid4()
    primeiro = L.registrar(db, usuario.id, contador.id, 1, token=token)
    segundo = L.registrar(db, usuario.id, contador.id, 1, token=token)
    assert primeiro.id == segundo.id
    assert total(db, usuario, contador) == 1


def test_token_de_outro_usuario_nao_e_reaproveitado(db, usuario, outro_usuario, contador):
    dela = service.criar_contador(db, outro_usuario.id, DadosContador("Água", "copo"))
    token = uuid.uuid4()
    L.registrar(db, outro_usuario.id, dela.id, 1, token=token)
    with pytest.raises(ErroValidacao):
        L.registrar(db, usuario.id, contador.id, 1, token=token)
    assert total(db, usuario, contador) == 0


def test_total_dia_respeita_fuso(db, usuario, contador, monkeypatch):
    agora = utc(2026, 10, 20, 1, 0)  # 22h do dia 19 em SP
    monkeypatch.setattr(tempo, "agora_utc", lambda: agora)
    L.registrar(db, usuario.id, contador.id, 5, ocorrido_em=utc(2026, 10, 19, 2, 30))  # 23:30 do dia 18
    L.registrar(db, usuario.id, contador.id, 2, ocorrido_em=utc(2026, 10, 20, 0, 30))  # 21:30 do dia 19
    assert total(db, usuario, contador, agora=agora) == 2


def test_totais_periodo_inclui_contador_sem_lancamentos(db, usuario, contador):
    assert L.totais_periodo(db, usuario.id, "dia", SP, AGORA) == {contador.id: 0}


def test_totais_por_mes_e_ano(db, usuario, contador):
    L.registrar(db, usuario.id, contador.id, 1, ocorrido_em=utc(2026, 10, 2, 15))
    L.registrar(db, usuario.id, contador.id, 2, ocorrido_em=utc(2026, 9, 30, 15))
    L.registrar(db, usuario.id, contador.id, 4, ocorrido_em=utc(2025, 12, 31, 15))
    assert total(db, usuario, contador, "mes") == 1
    assert total(db, usuario, contador, "ano") == 3


def test_desfazer_cancela_o_ultimo_registrado(db, usuario, contador):
    das_14 = L.registrar(db, usuario.id, contador.id, 1, ocorrido_em=utc(2026, 10, 19, 14))
    retroativo = L.registrar(db, usuario.id, contador.id, 1, ocorrido_em=utc(2026, 10, 19, 11))
    cancelado = L.desfazer_ultimo(db, usuario.id, contador.id, "dia", SP, AGORA)
    assert cancelado.id == retroativo.id
    assert cancelado.cancelado_em == AGORA
    db.refresh(das_14)
    assert das_14.cancelado_em is None
    assert total(db, usuario, contador) == 1


def test_desfazer_cancela_o_lancamento_inteiro(db, usuario, contador):
    L.registrar(db, usuario.id, contador.id, 1)
    L.registrar(db, usuario.id, contador.id, 30)
    L.desfazer_ultimo(db, usuario.id, contador.id, "dia", SP, AGORA)
    assert total(db, usuario, contador) == 1


def test_desfazer_ignora_ajuste(db, usuario):
    c = service.criar_contador(db, usuario.id, DadosContador("Treinos", "sessão"), valor_inicial=40)
    assert L.desfazer_ultimo(db, usuario.id, c.id, "ano", SP, AGORA) is None
    assert L.totais_periodo(db, usuario.id, "ano", SP, AGORA)[c.id] == 40


def test_desfazer_respeita_periodo(db, usuario, contador):
    ontem = L.registrar(db, usuario.id, contador.id, 1, ocorrido_em=AGORA - timedelta(days=1))
    assert L.desfazer_ultimo(db, usuario.id, contador.id, "dia", SP, AGORA) is None
    assert L.desfazer_ultimo(db, usuario.id, contador.id, "mes", SP, AGORA).id == ontem.id


def test_desfazer_nao_cancela_duas_vezes(db, usuario, contador):
    L.registrar(db, usuario.id, contador.id, 1)
    L.registrar(db, usuario.id, contador.id, 1)
    L.desfazer_ultimo(db, usuario.id, contador.id, "dia", SP, AGORA)
    L.desfazer_ultimo(db, usuario.id, contador.id, "dia", SP, AGORA)
    assert total(db, usuario, contador) == 0
    assert L.desfazer_ultimo(db, usuario.id, contador.id, "dia", SP, AGORA) is None


def test_pode_desfazer(db, usuario, contador):
    outro = service.criar_contador(db, usuario.id, DadosContador("Água", "copo"))
    L.registrar(db, usuario.id, contador.id, 1)
    assert L.pode_desfazer(db, usuario.id, "dia", SP, AGORA) == {contador.id}
    assert outro.id not in L.pode_desfazer(db, usuario.id, "dia", SP, AGORA)


def test_cancelar_nao_apaga(db, usuario, contador):
    lanc = L.registrar(db, usuario.id, contador.id, 3)
    L.cancelar(db, usuario.id, lanc.id)
    db.refresh(lanc)
    assert lanc.cancelado_em == AGORA
    assert total(db, usuario, contador) == 0
    assert [x.id for x in L.listar_lancamentos(db, usuario.id, contador.id, date(2026, 10, 19), date(2026, 10, 19), SP)] == [lanc.id]


def test_cancelar_duas_vezes_erro(db, usuario, contador):
    lanc = L.registrar(db, usuario.id, contador.id, 1)
    L.cancelar(db, usuario.id, lanc.id)
    with pytest.raises(ErroValidacao, match="Este lançamento já foi cancelado."):
        L.cancelar(db, usuario.id, lanc.id)


def test_corrigir_preserva_original(db, usuario, contador):
    original = L.registrar(db, usuario.id, contador.id, 1, ocorrido_em=utc(2026, 10, 19, 13))
    novo = L.corrigir(db, usuario.id, original.id, 3, utc(2026, 10, 19, 12))
    db.refresh(original)
    assert original.cancelado_em is not None
    assert (novo.substitui_id, novo.quantidade, novo.ocorrido_em, novo.tipo) == (original.id, 3, utc(2026, 10, 19, 12), "normal")
    assert total(db, usuario, contador) == 3


def test_corrigir_ajuste_continua_ajuste(db, usuario):
    c = service.criar_contador(db, usuario.id, DadosContador("Treinos", "sessão"), valor_inicial=40)
    [ajuste] = L.listar_lancamentos(db, usuario.id, c.id, date(2026, 10, 19), date(2026, 10, 19), SP)
    assert L.corrigir(db, usuario.id, ajuste.id, 42, ajuste.ocorrido_em).tipo == "ajuste"


def test_corrigir_cancelado_erro(db, usuario, contador):
    lanc = L.registrar(db, usuario.id, contador.id, 1)
    L.cancelar(db, usuario.id, lanc.id)
    with pytest.raises(ErroValidacao):
        L.corrigir(db, usuario.id, lanc.id, 2, AGORA)


def test_registrar_no_futuro_erro(db, usuario, contador):
    with pytest.raises(ErroValidacao, match="A data não pode estar no futuro."):
        L.registrar(db, usuario.id, contador.id, 1, ocorrido_em=AGORA + timedelta(hours=1))
    L.registrar(db, usuario.id, contador.id, 1, ocorrido_em=AGORA + timedelta(minutes=4))


def test_registrar_em_inativo_erro(db, usuario, contador):
    service.definir_ativo(db, usuario.id, contador.id, False)
    with pytest.raises(ErroValidacao, match="Este contador está inativo."):
        L.registrar(db, usuario.id, contador.id, 1)


def test_registrar_quantidade_invalida_erro(db, usuario, contador):
    with pytest.raises(ErroValidacao):
        L.registrar(db, usuario.id, contador.id, 0)


def test_totais_agrupados_distingue_vazio_de_zero(db, usuario, contador):
    cancelado = L.registrar(db, usuario.id, contador.id, 2, ocorrido_em=utc(2026, 10, 18, 15))
    L.cancelar(db, usuario.id, cancelado.id)
    L.registrar(db, usuario.id, contador.id, 3, ocorrido_em=utc(2026, 10, 19, 14))
    grupos = L.totais_agrupados(db, usuario.id, contador.id, date(2026, 10, 17), date(2026, 10, 19), "dia", SP)
    assert grupos == [
        TotalGrupo(date(2026, 10, 19), 3),
        TotalGrupo(date(2026, 10, 18), 0),
        TotalGrupo(date(2026, 10, 17), None),
    ]


def test_totais_agrupados_por_mes(db, usuario, contador):
    L.registrar(db, usuario.id, contador.id, 1, ocorrido_em=utc(2026, 10, 2, 15))
    L.registrar(db, usuario.id, contador.id, 2, ocorrido_em=utc(2026, 10, 1, 2, 0))  # 23h de 30/09 em SP
    grupos = L.totais_agrupados(db, usuario.id, contador.id, date(2026, 8, 15), date(2026, 10, 19), "mes", SP)
    assert grupos == [
        TotalGrupo(date(2026, 10, 1), 1),
        TotalGrupo(date(2026, 9, 1), 2),
        TotalGrupo(date(2026, 8, 1), None),
    ]


def test_totais_agrupados_por_ano(db, usuario, contador):
    L.registrar(db, usuario.id, contador.id, 1, ocorrido_em=utc(2026, 3, 2, 15))
    grupos = L.totais_agrupados(db, usuario.id, contador.id, date(2025, 6, 1), date(2026, 10, 19), "ano", SP)
    assert grupos == [TotalGrupo(date(2026, 1, 1), 1), TotalGrupo(date(2025, 1, 1), None)]


def test_listar_lancamentos_no_intervalo_e_ordenado(db, usuario, contador):
    a = L.registrar(db, usuario.id, contador.id, 1, ocorrido_em=utc(2026, 10, 18, 15))
    b = L.registrar(db, usuario.id, contador.id, 1, ocorrido_em=utc(2026, 10, 19, 14))
    L.registrar(db, usuario.id, contador.id, 1, ocorrido_em=utc(2026, 10, 10, 15))
    ids = [x.id for x in L.listar_lancamentos(db, usuario.id, contador.id, date(2026, 10, 18), date(2026, 10, 19), SP)]
    assert ids == [b.id, a.id]


def test_lancamento_de_outro_usuario_nao_encontrado(db, usuario, outro_usuario, contador):
    dela = service.criar_contador(db, outro_usuario.id, DadosContador("Água", "copo"))
    lanc = L.registrar(db, outro_usuario.id, dela.id, 1)
    with pytest.raises(NaoEncontrado):
        L.cancelar(db, usuario.id, lanc.id)
    with pytest.raises(NaoEncontrado):
        L.corrigir(db, usuario.id, lanc.id, 5, AGORA)
    with pytest.raises(NaoEncontrado):
        L.registrar(db, usuario.id, dela.id, 1)
    with pytest.raises(NaoEncontrado):
        L.listar_lancamentos(db, usuario.id, dela.id, date(2026, 10, 19), date(2026, 10, 19), SP)
    db.refresh(lanc)
    assert lanc.cancelado_em is None
