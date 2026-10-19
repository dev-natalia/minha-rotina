"""Administração de contas pela linha de comando.

Uso:
    uv run python -m app.cli criar-usuario --email ana@exemplo.com --nome Ana
    uv run python -m app.cli redefinir-senha --email ana@exemplo.com
    uv run python -m app.cli desativar-usuario --email ana@exemplo.com
"""

import argparse
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from getpass import getpass

from sqlalchemy.orm import Session

from app.auth import service
from app.erros import ErroValidacao, NaoEncontrado


@contextmanager
def abrir_sessao() -> Iterator[Session]:
    from app.db import SessionLocal

    with SessionLocal() as sessao:
        yield sessao


def _pedir_senha() -> str | None:
    senha = getpass("Senha: ")
    if getpass("Repita a senha: ") != senha:
        print("As senhas não conferem.", file=sys.stderr)
        return None
    return senha


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Contas do minha-rotina")
    sub = parser.add_subparsers(dest="comando", required=True)
    criar = sub.add_parser("criar-usuario", help="cria um usuário")
    criar.add_argument("--email", required=True)
    criar.add_argument("--nome", required=True)
    redefinir = sub.add_parser("redefinir-senha", help="define uma nova senha")
    redefinir.add_argument("--email", required=True)
    desativar = sub.add_parser("desativar-usuario", help="bloqueia o acesso de um usuário")
    desativar.add_argument("--email", required=True)
    args = parser.parse_args(argv)

    try:
        with abrir_sessao() as db:
            if args.comando == "criar-usuario":
                senha = _pedir_senha()
                if senha is None:
                    return 1
                usuario = service.criar_usuario(db, args.email, args.nome, senha)
                print(f"Usuário criado: {usuario.email}")
            elif args.comando == "redefinir-senha":
                senha = _pedir_senha()
                if senha is None:
                    return 1
                service.redefinir_senha(db, args.email, senha)
                print("Senha redefinida.")
            elif args.comando == "desativar-usuario":
                service.desativar_usuario(db, args.email)
                print("Usuário desativado.")
    except ErroValidacao as erro:
        print(erro.mensagem, file=sys.stderr)
        return 1
    except NaoEncontrado:
        print("Nenhum usuário com este email.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
