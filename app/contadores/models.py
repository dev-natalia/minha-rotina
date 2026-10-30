import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, String, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Contador(Base):
    __tablename__ = "contadores"
    __table_args__ = (
        CheckConstraint("passo >= 1", name="ck_contador_passo"),
        CheckConstraint("meta_valor IS NULL OR meta_valor >= 1", name="ck_contador_meta_valor"),
        CheckConstraint("meta_periodo IS NULL OR meta_periodo IN ('dia', 'mes', 'ano')", name="ck_contador_meta_periodo"),
        CheckConstraint("meta_sentido IS NULL OR meta_sentido IN ('maximo', 'minimo')", name="ck_contador_meta_sentido"),
        CheckConstraint(
            "(meta_valor IS NULL AND meta_periodo IS NULL AND meta_sentido IS NULL)"
            " OR (meta_valor IS NOT NULL AND meta_periodo IS NOT NULL AND meta_sentido IS NOT NULL)",
            name="ck_contador_meta_completa",
        ),
        # Alvo da FK composta de lancamentos: garante que o lançamento é do dono do contador.
        UniqueConstraint("id", "usuario_id", name="uq_contador_id_usuario"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    nome: Mapped[str] = mapped_column(String(60))
    unidade: Mapped[str] = mapped_column(String(30))
    passo: Mapped[int] = mapped_column(default=1)
    meta_valor: Mapped[int | None]
    meta_periodo: Mapped[str | None] = mapped_column(String(3))
    meta_sentido: Mapped[str | None] = mapped_column(String(6))
    ativo: Mapped[bool] = mapped_column(default=True)
    posicao: Mapped[int]
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class Lancamento(Base):
    """Uma ocorrência registrada. Nunca é apagada: cancelar marca `cancelado_em`."""

    __tablename__ = "lancamentos"
    __table_args__ = (
        CheckConstraint("quantidade > 0", name="ck_lancamento_quantidade"),
        CheckConstraint("tipo IN ('normal', 'ajuste')", name="ck_lancamento_tipo"),
        ForeignKeyConstraint(
            ["contador_id", "usuario_id"], ["contadores.id", "contadores.usuario_id"],
            ondelete="CASCADE", name="fk_lancamento_contador_usuario",
        ),
        Index("ix_lancamentos_contador_ocorrido", "contador_id", "ocorrido_em"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    contador_id: Mapped[int]
    usuario_id: Mapped[int] = mapped_column(index=True)
    quantidade: Mapped[int]
    ocorrido_em: Mapped[datetime]
    criado_em: Mapped[datetime] = mapped_column(server_default=func.clock_timestamp())
    tipo: Mapped[str] = mapped_column(String(6), default="normal")
    cancelado_em: Mapped[datetime | None]
    substitui_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("lancamentos.id"))
    token_cliente: Mapped[uuid.UUID | None] = mapped_column(Uuid, unique=True)
