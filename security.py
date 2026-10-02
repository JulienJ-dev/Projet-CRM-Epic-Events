"""Hachage et vérification des mots de passe avec Argon2id."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError


password_hasher = PasswordHasher()


def hash_password(password):
    """Valide le mot de passe et génère son hash avec un sel aléatoire."""
    if (
        not isinstance(password, str)
        or not 12 <= len(password) <= 128
        or not password.strip()
    ):
        raise ValueError("Le mot de passe doit contenir entre 12 et 128 caractères.")
    return password_hasher.hash(password)


def verify_password(password_hash, password):
    """Renvoie False si le mot de passe ou le hash est invalide."""
    if not isinstance(password, str) or len(password) > 128:
        return False
    try:
        return password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False
