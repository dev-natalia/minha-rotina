from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()


def hash_senha(senha: str) -> str:
    return _hasher.hash(senha)


def verificar_senha(hash: str, senha: str) -> bool:
    try:
        return _hasher.verify(hash, senha)
    except (VerificationError, InvalidHashError):
        return False
