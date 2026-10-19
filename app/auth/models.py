from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    nome: Mapped[str] = mapped_column(String(80))
    senha_hash: Mapped[str] = mapped_column(String(255))
    fuso_horario: Mapped[str] = mapped_column(String(64), default="America/Sao_Paulo")
    ativo: Mapped[bool] = mapped_column(default=True)
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())


class Sessao(Base):
    __tablename__ = "sessoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())
    expira_em: Mapped[datetime]

    usuario: Mapped[Usuario] = relationship(lazy="joined")


class TentativaLogin(Base):
    __tablename__ = "tentativas_login"
    __table_args__ = (Index("ix_tentativas_login_email_criado", "email", "criado_em"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254))
    ip: Mapped[str] = mapped_column(String(64), index=True)
    criado_em: Mapped[datetime]
