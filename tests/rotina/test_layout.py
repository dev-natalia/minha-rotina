from datetime import date, time

from app.rotina.layout import distribuir_faixas, faixa_horaria
from app.rotina.models import AtividadePlanejada


def ativ(inicio, fim, titulo="x"):
    return AtividadePlanejada(
        titulo=titulo, data=date(2026, 10, 19), hora_inicio=time(*inicio), hora_fim=time(*fim)
    )


def faixas(blocos):
    return [(b.atividade.titulo, b.faixa, b.total_faixas) for b in blocos]


def test_sem_sobreposicao_uma_faixa():
    blocos = distribuir_faixas([ativ((8, 0), (12, 0), "a"), ativ((12, 0), (13, 0), "b")])
    assert faixas(blocos) == [("a", 0, 1), ("b", 0, 1)]


def test_duas_sobrepostas_duas_faixas():
    blocos = distribuir_faixas([ativ((8, 0), (10, 0), "a"), ativ((9, 0), (11, 0), "b")])
    assert faixas(blocos) == [("a", 0, 2), ("b", 1, 2)]


def test_cadeia_transitiva():
    blocos = distribuir_faixas([
        ativ((8, 0), (10, 0), "a"), ativ((9, 0), (11, 0), "b"), ativ((10, 30), (12, 0), "c"),
    ])
    assert faixas(blocos) == [("a", 0, 2), ("b", 1, 2), ("c", 0, 2)]


def test_grupos_independentes_tem_totais_proprios():
    blocos = distribuir_faixas([
        ativ((8, 0), (10, 0), "a"), ativ((9, 0), (10, 0), "b"), ativ((14, 0), (15, 0), "c"),
    ])
    assert faixas(blocos) == [("a", 0, 2), ("b", 1, 2), ("c", 0, 1)]


def test_entrada_fora_de_ordem():
    blocos = distribuir_faixas([ativ((9, 0), (11, 0), "b"), ativ((8, 0), (10, 0), "a")])
    assert faixas(blocos) == [("a", 0, 2), ("b", 1, 2)]


def test_faixa_horaria_padrao_e_estendida():
    assert faixa_horaria([]) == (6, 23)
    assert faixa_horaria([ativ((5, 30), (7, 0))]) == (5, 23)
    assert faixa_horaria([ativ((22, 0), (23, 30))]) == (6, 24)
