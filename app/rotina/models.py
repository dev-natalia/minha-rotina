import uuid
from datetime import date, datetime, time

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AtividadePlanejada(Base):
    __tablename__ = "atividades_planejadas"
    __table_args__ = (
        CheckConstraint("hora_fim > hora_inicio", name="ck_atividade_fim_depois_do_inicio"),
        Index("ix_atividades_usuario_data", "usuario_id", "data"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    data: Mapped[date]
    hora_inicio: Mapped[time]
    hora_fim: Mapped[time]
    titulo: Mapped[str] = mapped_column(String(120))
    descricao: Mapped[str | None] = mapped_column(Text)
    cor: Mapped[str | None] = mapped_column(String(20))
    grupo_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
