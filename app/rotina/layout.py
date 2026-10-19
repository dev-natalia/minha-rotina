"""Posicionamento das atividades na grade (sobreposições lado a lado)."""

from dataclasses import dataclass
from math import ceil

from app.rotina.models import AtividadePlanejada

HORA_INICIAL_PADRAO = 6
HORA_FINAL_PADRAO = 23


@dataclass
class BlocoLayout:
    atividade: AtividadePlanejada
    faixa: int
    total_faixas: int


def distribuir_faixas(atividades: list[AtividadePlanejada]) -> list[BlocoLayout]:
    """Para as atividades de um dia: cada grupo de sobreposição recebe faixas próprias."""
    ordenadas = sorted(atividades, key=lambda a: (a.hora_inicio, a.hora_fim))
    resultado: list[BlocoLayout] = []
    grupo: list[BlocoLayout] = []
    fins_das_faixas: list = []  # fim da última atividade em cada faixa do grupo atual
    fim_do_grupo = None

    def fechar_grupo():
        for bloco in grupo:
            bloco.total_faixas = len(fins_das_faixas)
        resultado.extend(grupo)

    for atividade in ordenadas:
        if fim_do_grupo is not None and atividade.hora_inicio >= fim_do_grupo:
            fechar_grupo()
            grupo, fins_das_faixas, fim_do_grupo = [], [], None
        faixa = next((i for i, fim in enumerate(fins_das_faixas) if fim <= atividade.hora_inicio), None)
        if faixa is None:
            faixa = len(fins_das_faixas)
            fins_das_faixas.append(atividade.hora_fim)
        else:
            fins_das_faixas[faixa] = atividade.hora_fim
        grupo.append(BlocoLayout(atividade, faixa, 0))
        fim_do_grupo = atividade.hora_fim if fim_do_grupo is None else max(fim_do_grupo, atividade.hora_fim)

    fechar_grupo()
    return resultado


def faixa_horaria(atividades: list[AtividadePlanejada]) -> tuple[int, int]:
    """Horas inteiras visíveis na grade: pelo menos 6h–23h, estendendo para caber tudo."""
    inicio, fim = HORA_INICIAL_PADRAO, HORA_FINAL_PADRAO
    for a in atividades:
        inicio = min(inicio, a.hora_inicio.hour)
        fim = max(fim, ceil(a.hora_fim.hour + a.hora_fim.minute / 60))
    return inicio, fim
