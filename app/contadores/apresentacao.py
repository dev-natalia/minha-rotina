"""Textos exibidos nos cartões de contador."""

from app.contadores.models import Contador
from app.tempo import Periodo

ROTULO_PERIODO = {"dia": "hoje", "mes": "este mês", "ano": "este ano"}
NOME_PERIODO = {"dia": "Dia", "mes": "Mês", "ano": "Ano"}
PERIODO_DA_META = {"dia": "por dia", "mes": "por mês", "ano": "por ano"}


def texto_meta(contador: Contador, total: int, periodo: Periodo) -> str | None:
    if contador.meta_valor is None or contador.meta_periodo != periodo:
        return None
    meta = contador.meta_valor
    if contador.meta_sentido == "maximo":
        texto = f"{total} de no máximo {meta}"
        return f"{texto} · acima da meta" if total > meta else texto
    texto = f"{total} de {meta}"
    return f"{texto} · meta atingida" if total >= meta else texto


def descricao_meta(contador: Contador) -> str | None:
    """Ex.: "no máximo 5 por dia" (usado na tela de gerenciar)."""
    if contador.meta_valor is None:
        return None
    sentido = "no máximo" if contador.meta_sentido == "maximo" else "pelo menos"
    return f"{sentido} {contador.meta_valor} {PERIODO_DA_META[contador.meta_periodo]}"
