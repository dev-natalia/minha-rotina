from datetime import date, datetime
from datetime import timezone as tz

from app import tempo

SP = "America/Sao_Paulo"


def test_limites_dia_em_sao_paulo():
    agora = datetime(2026, 10, 20, 2, 30, tzinfo=tz.utc)  # 23:30 do dia 19 em SP
    ini, fim = tempo.limites_periodo("dia", agora, SP)
    assert ini == datetime(2026, 10, 19, 3, 0, tzinfo=tz.utc)
    assert fim == datetime(2026, 10, 20, 3, 0, tzinfo=tz.utc)


def test_limites_mes_e_ano():
    agora = datetime(2026, 10, 19, 15, 0, tzinfo=tz.utc)
    assert tempo.limites_periodo("mes", agora, SP) == (
        datetime(2026, 10, 1, 3, tzinfo=tz.utc),
        datetime(2026, 11, 1, 3, tzinfo=tz.utc),
    )
    assert tempo.limites_periodo("ano", agora, SP) == (
        datetime(2026, 1, 1, 3, tzinfo=tz.utc),
        datetime(2027, 1, 1, 3, tzinfo=tz.utc),
    )


def test_limites_mes_de_dezembro_vira_o_ano():
    agora = datetime(2026, 12, 15, 15, 0, tzinfo=tz.utc)
    _, fim = tempo.limites_periodo("mes", agora, SP)
    assert fim == datetime(2027, 1, 1, 3, tzinfo=tz.utc)


def test_hoje_local():
    agora = datetime(2026, 10, 20, 2, 30, tzinfo=tz.utc)
    assert tempo.hoje_local(SP, agora) == date(2026, 10, 19)


def test_inicio_semana_e_segunda():
    assert tempo.inicio_semana(date(2026, 10, 25)) == date(2026, 10, 19)  # domingo
    assert tempo.inicio_semana(date(2026, 10, 19)) == date(2026, 10, 19)


def test_limites_datas_inclui_o_ultimo_dia():
    ini, fim = tempo.limites_datas(date(2026, 10, 1), date(2026, 10, 31), SP)
    assert ini == datetime(2026, 10, 1, 3, tzinfo=tz.utc)
    assert fim == datetime(2026, 11, 1, 3, tzinfo=tz.utc)


def test_data_por_extenso():
    assert tempo.data_por_extenso(date(2026, 10, 19)) == "Segunda-feira, 19 de outubro"
    assert tempo.data_por_extenso(date(2026, 3, 1)) == "Domingo, 1 de março"


def test_fuso_valido():
    assert tempo.fuso_valido(SP)
    assert not tempo.fuso_valido("Marte/Base")


def test_agora_utc_tem_fuso():
    assert tempo.agora_utc().tzinfo is not None
