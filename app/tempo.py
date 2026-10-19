"""Tempo e fuso: tudo é gravado em UTC e interpretado no fuso do usuário."""

from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, available_timezones

Periodo = Literal["dia", "mes", "ano"]

NOMES_DIAS_CURTOS = ("S", "T", "Q", "Q", "S", "S", "D")
NOMES_DIAS = ("Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo")
_DIAS_EXTENSO = (
    "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
    "Sexta-feira", "Sábado", "Domingo",
)
_MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def agora_utc() -> datetime:
    """Único ponto de "agora" do app (os testes substituem esta função)."""
    return datetime.now(UTC)


def local(instante: datetime, fuso: str) -> datetime:
    return instante.astimezone(ZoneInfo(fuso))


def hoje_local(fuso: str, agora: datetime) -> date:
    return local(agora, fuso).date()


def _meia_noite_utc(d: date, fuso: str) -> datetime:
    return datetime.combine(d, time(0), tzinfo=ZoneInfo(fuso)).astimezone(UTC)


def limites_periodo(periodo: Periodo, agora: datetime, fuso: str) -> tuple[datetime, datetime]:
    """Intervalo [inicio, fim) em UTC do dia/mês/ano local que contém `agora`."""
    hoje = hoje_local(fuso, agora)
    if periodo == "dia":
        inicio, fim = hoje, hoje + timedelta(days=1)
    elif periodo == "mes":
        inicio = hoje.replace(day=1)
        fim = date(hoje.year + 1, 1, 1) if hoje.month == 12 else date(hoje.year, hoje.month + 1, 1)
    elif periodo == "ano":
        inicio, fim = date(hoje.year, 1, 1), date(hoje.year + 1, 1, 1)
    else:
        raise ValueError(f"Período inválido: {periodo}")
    return _meia_noite_utc(inicio, fuso), _meia_noite_utc(fim, fuso)


def limites_datas(de: date, ate: date, fuso: str) -> tuple[datetime, datetime]:
    """Intervalo [de 00:00, ate+1 00:00) local, em UTC."""
    return _meia_noite_utc(de, fuso), _meia_noite_utc(ate + timedelta(days=1), fuso)


def inicio_semana(d: date) -> date:
    return d - timedelta(days=d.weekday())


@lru_cache
def _fusos() -> frozenset[str]:
    return frozenset(available_timezones())


def fuso_valido(fuso: str) -> bool:
    return fuso in _fusos()


def data_por_extenso(d: date) -> str:
    return f"{_DIAS_EXTENSO[d.weekday()]}, {d.day} de {_MESES[d.month - 1]}"
