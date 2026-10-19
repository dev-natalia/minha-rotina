"""Lançamentos e totais. Totais são sempre somas dos lançamentos não cancelados."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import and_, case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import tempo
from app.contadores.models import Contador, Lancamento
from app.contadores.service import VALOR_MAXIMO, obter_contador
from app.erros import ErroValidacao, NaoEncontrado
from app.tempo import Periodo

TOLERANCIA_FUTURO = timedelta(minutes=5)


@dataclass(frozen=True)
class TotalGrupo:
    inicio: date
    total: int | None  # None = nenhum lançamento no grupo; 0 = só cancelados


def _validar_quantidade(quantidade: int) -> None:
    if not 1 <= quantidade <= VALOR_MAXIMO:
        raise ErroValidacao(f"Quantidade: informe um número inteiro entre 1 e {VALOR_MAXIMO}.")


def _validar_momento(ocorrido_em: datetime) -> None:
    if ocorrido_em > tempo.agora_utc() + TOLERANCIA_FUTURO:
        raise ErroValidacao("A data não pode estar no futuro.")


def _por_token(db: Session, token: uuid.UUID) -> Lancamento | None:
    return db.scalar(select(Lancamento).where(Lancamento.token_cliente == token))


def _do_token(existente: Lancamento, usuario_id: int) -> Lancamento:
    if existente.usuario_id != usuario_id:
        raise ErroValidacao("Não foi possível registrar. Recarregue a página e tente de novo.")
    return existente


def registrar(
    db: Session,
    usuario_id: int,
    contador_id: int,
    quantidade: int,
    token: uuid.UUID | None = None,
    ocorrido_em: datetime | None = None,
) -> Lancamento:
    contador = obter_contador(db, usuario_id, contador_id)
    if token is not None and (existente := _por_token(db, token)) is not None:
        return _do_token(existente, usuario_id)  # toque repetido: não duplica
    if not contador.ativo:
        raise ErroValidacao("Este contador está inativo.")
    _validar_quantidade(quantidade)
    ocorrido_em = ocorrido_em or tempo.agora_utc()
    _validar_momento(ocorrido_em)

    lancamento = Lancamento(
        contador_id=contador_id, usuario_id=usuario_id, quantidade=quantidade,
        ocorrido_em=ocorrido_em, tipo="normal", token_cliente=token,
    )
    try:
        with db.begin_nested():
            db.add(lancamento)
    except IntegrityError:
        # Dois envios do mesmo toque ao mesmo tempo: o outro chegou primeiro.
        existente = _por_token(db, token) if token is not None else None
        if existente is None:
            raise
        return _do_token(existente, usuario_id)
    db.commit()
    return lancamento


def _obter_lancamento(db: Session, usuario_id: int, lancamento_id: int) -> Lancamento:
    lancamento = db.get(Lancamento, lancamento_id, with_for_update=True)
    if lancamento is None or lancamento.usuario_id != usuario_id:
        raise NaoEncontrado()
    return lancamento


def _filtro_validos_no_periodo(inicio: datetime, fim: datetime):
    return and_(Lancamento.cancelado_em.is_(None), Lancamento.ocorrido_em >= inicio, Lancamento.ocorrido_em < fim)


def desfazer_ultimo(
    db: Session, usuario_id: int, contador_id: int, periodo: Periodo, fuso: str, agora: datetime
) -> Lancamento | None:
    obter_contador(db, usuario_id, contador_id)
    inicio, fim = tempo.limites_periodo(periodo, agora, fuso)
    ultimo = db.scalar(
        select(Lancamento)
        .where(
            Lancamento.contador_id == contador_id,
            Lancamento.usuario_id == usuario_id,
            Lancamento.tipo == "normal",
            _filtro_validos_no_periodo(inicio, fim),
        )
        .order_by(Lancamento.criado_em.desc(), Lancamento.id.desc())
        .limit(1)
        .with_for_update()
    )
    if ultimo is None:
        return None
    ultimo.cancelado_em = tempo.agora_utc()
    db.commit()
    return ultimo


def cancelar(db: Session, usuario_id: int, lancamento_id: int) -> Lancamento:
    lancamento = _obter_lancamento(db, usuario_id, lancamento_id)
    if lancamento.cancelado_em is not None:
        raise ErroValidacao("Este lançamento já foi cancelado.")
    lancamento.cancelado_em = tempo.agora_utc()
    db.commit()
    return lancamento


def corrigir(db: Session, usuario_id: int, lancamento_id: int, quantidade: int, ocorrido_em: datetime) -> Lancamento:
    original = _obter_lancamento(db, usuario_id, lancamento_id)
    if original.cancelado_em is not None:
        raise ErroValidacao("Este lançamento já foi cancelado.")
    _validar_quantidade(quantidade)
    _validar_momento(ocorrido_em)
    original.cancelado_em = tempo.agora_utc()
    novo = Lancamento(
        contador_id=original.contador_id, usuario_id=usuario_id, quantidade=quantidade,
        ocorrido_em=ocorrido_em, tipo=original.tipo, substitui_id=original.id,
    )
    db.add(novo)
    db.commit()
    return novo


def totais_periodo(db: Session, usuario_id: int, periodo: Periodo, fuso: str, agora: datetime) -> dict[int, int]:
    inicio, fim = tempo.limites_periodo(periodo, agora, fuso)
    linhas = db.execute(
        select(Contador.id, func.coalesce(func.sum(Lancamento.quantidade), 0))
        .outerjoin(Lancamento, and_(Lancamento.contador_id == Contador.id, _filtro_validos_no_periodo(inicio, fim)))
        .where(Contador.usuario_id == usuario_id)
        .group_by(Contador.id)
    )
    return {contador_id: int(soma) for contador_id, soma in linhas}


def pode_desfazer(db: Session, usuario_id: int, periodo: Periodo, fuso: str, agora: datetime) -> set[int]:
    inicio, fim = tempo.limites_periodo(periodo, agora, fuso)
    return set(db.scalars(
        select(Lancamento.contador_id).distinct().where(
            Lancamento.usuario_id == usuario_id,
            Lancamento.tipo == "normal",
            _filtro_validos_no_periodo(inicio, fim),
        )
    ))


def _truncar(d: date, agrupar: Periodo) -> date:
    if agrupar == "mes":
        return d.replace(day=1)
    if agrupar == "ano":
        return d.replace(month=1, day=1)
    return d


def _anterior(d: date, agrupar: Periodo) -> date:
    if agrupar == "mes":
        return date(d.year - 1, 12, 1) if d.month == 1 else date(d.year, d.month - 1, 1)
    if agrupar == "ano":
        return date(d.year - 1, 1, 1)
    return d - timedelta(days=1)


def totais_agrupados(
    db: Session, usuario_id: int, contador_id: int, de: date, ate: date, agrupar: Periodo, fuso: str
) -> list[TotalGrupo]:
    obter_contador(db, usuario_id, contador_id)
    inicio, fim = tempo.limites_datas(de, ate, fuso)
    unidade = {"dia": "day", "mes": "month", "ano": "year"}[agrupar]
    grupo = func.date_trunc(unidade, func.timezone(fuso, Lancamento.ocorrido_em))
    linhas = db.execute(
        select(grupo, func.sum(case((Lancamento.cancelado_em.is_(None), Lancamento.quantidade), else_=0)))
        .where(
            Lancamento.contador_id == contador_id,
            Lancamento.usuario_id == usuario_id,
            Lancamento.ocorrido_em >= inicio,
            Lancamento.ocorrido_em < fim,
        )
        .group_by(grupo)
    )
    somas = {g.date(): int(soma) for g, soma in linhas}

    resultado = []
    atual, primeiro = _truncar(ate, agrupar), _truncar(de, agrupar)
    while atual >= primeiro:
        resultado.append(TotalGrupo(atual, somas.get(atual)))
        atual = _anterior(atual, agrupar)
    return resultado


def listar_lancamentos(
    db: Session, usuario_id: int, contador_id: int, de: date, ate: date, fuso: str
) -> list[Lancamento]:
    obter_contador(db, usuario_id, contador_id)
    inicio, fim = tempo.limites_datas(de, ate, fuso)
    return list(db.scalars(
        select(Lancamento)
        .where(
            Lancamento.contador_id == contador_id,
            Lancamento.usuario_id == usuario_id,
            Lancamento.ocorrido_em >= inicio,
            Lancamento.ocorrido_em < fim,
        )
        .order_by(Lancamento.ocorrido_em.desc(), Lancamento.id.desc())
    ))
