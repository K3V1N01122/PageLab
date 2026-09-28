"""Primitivas de seguridad: hashing de contraseñas y tokens."""
import hashlib
import hmac
import secrets

from werkzeug.security import check_password_hash, generate_password_hash

# scrypt con parámetros por defecto de Werkzeug (n=2**15, r=8, p=1), con sal.
PASSWORD_METHOD = "scrypt"
_DUMMY_HASH = generate_password_hash("timing-equalizer", method=PASSWORD_METHOD)


def hash_password(password: str) -> str:
    return generate_password_hash(password, method=PASSWORD_METHOD)


def verify_password(password_hash: str | None, password: str) -> bool:
    # Si el usuario no existe se verifica contra un hash ficticio para que el
    # tiempo de respuesta no revele qué correos están registrados.
    return check_password_hash(password_hash or _DUMMY_HASH, password) and password_hash is not None


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def token_hash(token: str) -> str:
    """Los tokens (sesión, recuperación) se guardan hasheados: si la BD se
    filtra, no sirven para suplantar a nadie."""
    return hashlib.sha256(token.encode()).hexdigest()


def constant_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # sin 0/O/1/I para lectura humana


def human_code(length: int = 8) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))
