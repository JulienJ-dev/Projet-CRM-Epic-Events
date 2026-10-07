"""Authentification persistante et autorisation de l'utilisateur courant."""

import hmac
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from accounts import authenticate
from models import Collaborator
from permissions import require_permission


ALGORITHM = "HS256"
ISSUER = "epic-events"
AUDIENCE = "epic-events-cli"
TOKEN_LIFETIME = timedelta(hours=8)


class AuthenticationError(Exception):
    """Signale l'absence d'une session valide."""


def get_secret_key():
    """Charge le secret de signature depuis la configuration locale."""
    secret = os.getenv("JWT_SECRET_KEY", "")
    if len(secret.encode("utf-8")) < 32 or not secret.strip():
        raise ValueError(
            "Configurez JWT_SECRET_KEY avec un secret aléatoire d'au moins 32 octets."
        )
    return secret


def get_token_file():
    """Renvoie le fichier local contenant le jeton de session."""
    default_path = Path(__file__).with_name(".session_token")
    token_file = Path(os.getenv("SESSION_TOKEN_FILE") or default_path)
    if not token_file.is_absolute():
        token_file = Path(__file__).parent / token_file
    return token_file


def credential_fingerprint(user):
    """Lie le jeton aux identifiants actuels sans exposer le hash du mot de passe."""
    return hmac.new(
        get_secret_key().encode("utf-8"),
        user.password_hash.encode("utf-8"),
        digestmod="sha256",
    ).hexdigest()


def create_token(user):
    """Signe un jeton contenant le numéro d'employé et une expiration."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "iat": now,
        "exp": now + TOKEN_LIFETIME,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "credential": credential_fingerprint(user),
    }
    return jwt.encode(payload, get_secret_key(), algorithm=ALGORITHM)


def decode_token(token):
    """Vérifie la signature, l'algorithme autorisé et les dates du jeton."""
    secret = get_secret_key()
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={"require": ["sub", "iat", "exp", "iss", "aud", "credential"]},
        )
        employee_id = int(payload["sub"])
        if employee_id <= 0 or str(employee_id) != payload["sub"]:
            raise jwt.InvalidTokenError()
        if (
            not isinstance(payload["credential"], str)
            or not payload["credential"].isascii()
            or len(payload["credential"]) != 64
        ):
            raise jwt.InvalidTokenError()
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError(
            "Session expirée. Reconnectez-vous avec epicevents.py login."
        ) from None
    except (jwt.InvalidTokenError, TypeError, ValueError):
        raise AuthenticationError(
            "Session invalide. Reconnectez-vous avec epicevents.py login."
        ) from None


def save_token(token):
    """Remplace le fichier de session après une écriture complète du jeton."""
    token_file = get_token_file()
    token_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=token_file.parent,
            prefix=token_file.name + ".",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(token)
        os.replace(temporary_path, token_file)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def login(session, email, password):
    """Vérifie les identifiants et enregistre le jeton localement."""
    user = authenticate(session, email, password)
    if user is None:
        raise AuthenticationError("Email ou mot de passe incorrect.")
    save_token(create_token(user))
    return user


def logout():
    """Supprime le jeton enregistré sur cette machine."""
    get_token_file().unlink(missing_ok=True)


def get_current_user(session):
    """Relit le jeton et le compte en base à chaque appel."""
    try:
        token = get_token_file().read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise AuthenticationError("Connectez-vous avec epicevents.py login.") from None
    except UnicodeDecodeError:
        logout()
        raise AuthenticationError("Session illisible. Reconnectez-vous.") from None
    try:
        payload = decode_token(token)
        employee_id = int(payload["sub"])
        user = session.scalar(
            select(Collaborator)
            .where(Collaborator.id == employee_id)
            .options(joinedload(Collaborator.role))
            .execution_options(populate_existing=True)
        )
        if user is None:
            raise AuthenticationError("Ce compte n'existe plus. Reconnectez-vous.")
        if not hmac.compare_digest(payload["credential"], credential_fingerprint(user)):
            raise AuthenticationError(
                "Identifiants du compte modifiés. Reconnectez-vous."
            )
        return user
    except AuthenticationError:
        logout()
        raise


def authorize_current_user(session, action, resource=None):
    """Vérifie les droits actuels du compte identifié par le jeton local."""
    user = get_current_user(session)
    require_permission(user, action, resource)
    return user
