"""Regras da rotina semanal: cada semana tem o próprio planejamento, com datas reais."""

import uuid
from dataclasses import dataclass, replace
from datetime import date, time, timedelta
from typing import Literal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.erros import ErroValidacao, NaoEncontrado
from app.rotina.models import AtividadePlanejada
from app.tempo import inicio_semana

CORES = ("verde", "areia", "lavanda", "azul", "rosa")
TAMANHO_MAXIMO_TITULO = 120

Escopo = Literal["dia", "grupo"]


@dataclass(frozen=True)
class DadosAtividade:
    titulo: str
    hora_inicio: time
    hora_fim: time
    descricao: str | None = None
    cor: str | None = None


def validar_dados(dados: DadosAtividade) -> DadosAtividade:
    titulo = dados.titulo.strip()
    descricao = (dados.descricao or "").strip() or None
    cor = (dados.cor or "").strip() or None
    if not titulo:
        raise ErroValidacao("Informe um título.")
    if len(titulo) > TAMANHO_MAXIMO_TITULO:
        raise ErroValidacao(f"O título pode ter até {TAMANHO_MAXIMO_TITULO} caracteres.")
    if dados.hora_fim <= dados.hora_inicio:
        raise ErroValidacao("O horário de fim deve ser depois do início.")
    if cor is not None and cor not in CORES:
        raise ErroValidacao("Cor inválida.")
    return replace(dados, titulo=titulo, descricao=descricao, cor=cor)


def _aplicar(atividade: AtividadePlanejada, dados: DadosAtividade) -> None:
    atividade.titulo = dados.titulo
    atividade.hora_inicio = dados.hora_inicio
    atividade.hora_fim = dados.hora_fim
    atividade.descricao = dados.descricao
    atividade.cor = dados.cor


def criar_atividades(
    db: Session, usuario_id: int, semana: date, dias: list[int], dados: DadosAtividade
) -> list[AtividadePlanejada]:
    dados = validar_dados(dados)
    dias = sorted(set(dias))
    if not dias:
        raise ErroValidacao("Escolha pelo menos um dia.")
    if any(d < 0 or d > 6 for d in dias):
        raise ErroValidacao("Dia da semana inválido.")
    segunda = inicio_semana(semana)
    grupo_id = uuid.uuid4() if len(dias) > 1 else None
    criadas = []
    for dia in dias:
        atividade = AtividadePlanejada(usuario_id=usuario_id, data=segunda + timedelta(days=dia), grupo_id=grupo_id)
        _aplicar(atividade, dados)
        db.add(atividade)
        criadas.append(atividade)
    db.commit()
    return criadas


def _ordem():
    return (AtividadePlanejada.data, AtividadePlanejada.hora_inicio, AtividadePlanejada.titulo, AtividadePlanejada.id)


def listar_semana(db: Session, usuario_id: int, semana: date) -> list[AtividadePlanejada]:
    segunda = inicio_semana(semana)
    return list(db.scalars(
        select(AtividadePlanejada)
        .where(
            AtividadePlanejada.usuario_id == usuario_id,
            AtividadePlanejada.data >= segunda,
            AtividadePlanejada.data < segunda + timedelta(days=7),
        )
        .order_by(*_ordem())
    ))


def listar_dia(db: Session, usuario_id: int, dia: date) -> list[AtividadePlanejada]:
    return list(db.scalars(
        select(AtividadePlanejada)
        .where(AtividadePlanejada.usuario_id == usuario_id, AtividadePlanejada.data == dia)
        .order_by(*_ordem())
    ))


def obter_atividade(db: Session, usuario_id: int, atividade_id: int) -> AtividadePlanejada:
    atividade = db.get(AtividadePlanejada, atividade_id)
    if atividade is None or atividade.usuario_id != usuario_id:
        raise NaoEncontrado()
    return atividade


def _do_grupo(db: Session, atividade: AtividadePlanejada) -> list[AtividadePlanejada]:
    return list(db.scalars(
        select(AtividadePlanejada).where(
            AtividadePlanejada.usuario_id == atividade.usuario_id,
            AtividadePlanejada.grupo_id == atividade.grupo_id,
        )
    ))


def atualizar_atividade(
    db: Session, usuario_id: int, atividade_id: int, dados: DadosAtividade, escopo: Escopo
) -> None:
    atividade = obter_atividade(db, usuario_id, atividade_id)
    dados = validar_dados(dados)
    if escopo == "grupo" and atividade.grupo_id is not None:
        for outra in _do_grupo(db, atividade):
            _aplicar(outra, dados)
    else:
        # Ajuste pontual: o dia sai do grupo para uma edição futura em "todos" não sobrescrevê-lo.
        _aplicar(atividade, dados)
        atividade.grupo_id = None
    db.commit()


def excluir_atividade(db: Session, usuario_id: int, atividade_id: int, escopo: Escopo) -> None:
    atividade = obter_atividade(db, usuario_id, atividade_id)
    alvos = _do_grupo(db, atividade) if escopo == "grupo" and atividade.grupo_id is not None else [atividade]
    for alvo in alvos:
        db.delete(alvo)
    db.commit()


def copiar_semana_anterior(db: Session, usuario_id: int, semana: date) -> int:
    segunda = inicio_semana(semana)
    origem = listar_semana(db, usuario_id, segunda - timedelta(days=7))
    if not origem:
        raise ErroValidacao("A semana anterior não tem atividades.")
    db.execute(
        delete(AtividadePlanejada).where(
            AtividadePlanejada.usuario_id == usuario_id,
            AtividadePlanejada.data >= segunda,
            AtividadePlanejada.data < segunda + timedelta(days=7),
        )
    )
    novos_grupos: dict[uuid.UUID, uuid.UUID] = {}
    for antiga in origem:
        grupo = None
        if antiga.grupo_id is not None:
            grupo = novos_grupos.setdefault(antiga.grupo_id, uuid.uuid4())
        db.add(AtividadePlanejada(
            usuario_id=usuario_id,
            data=antiga.data + timedelta(days=7),
            hora_inicio=antiga.hora_inicio,
            hora_fim=antiga.hora_fim,
            titulo=antiga.titulo,
            descricao=antiga.descricao,
            cor=antiga.cor,
            grupo_id=grupo,
        ))
    db.commit()
    return len(origem)
