"""Configuração dos contadores (criar, editar, ativar/desativar)."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import tempo
from app.contadores.models import Contador, Lancamento
from app.erros import ErroValidacao, NaoEncontrado

PERIODOS_META = ("dia", "mes", "ano")
SENTIDOS_META = ("maximo", "minimo")
VALOR_MAXIMO = 1_000_000


@dataclass(frozen=True)
class DadosContador:
    nome: str
    unidade: str
    passo: int = 1
    meta_valor: int | None = None
    meta_periodo: str | None = None
    meta_sentido: str | None = None


def ler_inteiro(valor: str, campo: str, minimo: int = 1, maximo: int = VALOR_MAXIMO) -> int:
    texto = (valor or "").strip()
    erro = ErroValidacao(f"{campo}: informe um número inteiro entre {minimo} e {maximo}.")
    if not texto.lstrip("-").isdigit():
        raise erro
    numero = int(texto)
    if not minimo <= numero <= maximo:
        raise erro
    return numero


def _validar(dados: DadosContador) -> DadosContador:
    nome, unidade = dados.nome.strip(), dados.unidade.strip()
    if not nome:
        raise ErroValidacao("Informe um nome.")
    if len(nome) > 60:
        raise ErroValidacao("O nome pode ter até 60 caracteres.")
    if not unidade:
        raise ErroValidacao("Informe a unidade.")
    if len(unidade) > 30:
        raise ErroValidacao("A unidade pode ter até 30 caracteres.")
    if not 1 <= dados.passo <= VALOR_MAXIMO:
        raise ErroValidacao(f"Passo: informe um número inteiro entre 1 e {VALOR_MAXIMO}.")
    meta = (dados.meta_valor, dados.meta_periodo or None, dados.meta_sentido or None)
    if any(v is not None for v in meta):
        if any(v is None for v in meta):
            raise ErroValidacao("Para definir uma meta, preencha valor, período e sentido.")
        if meta[1] not in PERIODOS_META or meta[2] not in SENTIDOS_META:
            raise ErroValidacao("Meta inválida.")
        if not 1 <= meta[0] <= VALOR_MAXIMO:
            raise ErroValidacao(f"Meta: informe um número inteiro entre 1 e {VALOR_MAXIMO}.")
    return DadosContador(nome, unidade, dados.passo, *meta)


def _aplicar(contador: Contador, dados: DadosContador) -> None:
    contador.nome = dados.nome
    contador.unidade = dados.unidade
    contador.passo = dados.passo
    contador.meta_valor = dados.meta_valor
    contador.meta_periodo = dados.meta_periodo
    contador.meta_sentido = dados.meta_sentido


def criar_contador(
    db: Session,
    usuario_id: int,
    dados: DadosContador,
    valor_inicial: int | None = None,
    valor_inicial_em: datetime | None = None,
) -> Contador:
    dados = _validar(dados)
    ultima = db.scalar(select(func.max(Contador.posicao)).where(Contador.usuario_id == usuario_id))
    contador = Contador(usuario_id=usuario_id, posicao=(ultima or 0) + 1)
    _aplicar(contador, dados)
    db.add(contador)
    db.flush()
    if valor_inicial:
        # O valor de antes do app vira um lançamento de ajuste, para o total bater com o histórico.
        db.add(Lancamento(
            contador_id=contador.id, usuario_id=usuario_id, quantidade=valor_inicial, tipo="ajuste",
            ocorrido_em=valor_inicial_em or tempo.agora_utc(),
        ))
    db.commit()
    return contador


def obter_contador(db: Session, usuario_id: int, contador_id: int) -> Contador:
    contador = db.get(Contador, contador_id)
    if contador is None or contador.usuario_id != usuario_id:
        raise NaoEncontrado()
    return contador


def atualizar_contador(db: Session, usuario_id: int, contador_id: int, dados: DadosContador) -> None:
    contador = obter_contador(db, usuario_id, contador_id)
    _aplicar(contador, _validar(dados))
    db.commit()


def definir_ativo(db: Session, usuario_id: int, contador_id: int, ativo: bool) -> None:
    obter_contador(db, usuario_id, contador_id).ativo = ativo
    db.commit()


def listar_contadores(db: Session, usuario_id: int, ativos: bool | None = True) -> list[Contador]:
    consulta = select(Contador).where(Contador.usuario_id == usuario_id)
    if ativos is not None:
        consulta = consulta.where(Contador.ativo.is_(ativos))
    return list(db.scalars(consulta.order_by(Contador.posicao, Contador.id)))
