"""Création des comptes et authentification des collaborateurs."""

import re
import secrets

from sqlalchemy import select

from models import Collaborator, Role
from permissions import require_permission
from security import hash_password, password_hasher, verify_password


# Permet aussi de vérifier un hash quand l'adresse email n'existe pas.
DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(32))


def normalize_email(email):
    """Normalise l'identifiant utilisé à la création et à la connexion."""
    return email.strip().lower()


def _add_collaborator(session, full_name, email, password, role_name):
    full_name = full_name.strip()
    email = normalize_email(email)
    if not full_name or len(full_name) > 100:
        raise ValueError("Le nom doit contenir entre 1 et 100 caractères.")
    if len(email) > 255 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("L'adresse email est invalide.")
    if session.scalar(select(Collaborator).where(Collaborator.email == email)):
        raise ValueError("Cette adresse email est déjà utilisée.")
    role = session.scalar(select(Role).where(Role.name == role_name))
    if role is None:
        raise ValueError("Département inconnu. Initialisez les rôles avec init_db.py.")
    user = Collaborator(
        full_name=full_name,
        email=email,
        password_hash=hash_password(password),
        role=role,
    )
    session.add(user)
    session.flush()
    return user


def create_collaborator(session, actor, full_name, email, password, role_name):
    """Crée un compte à la demande d'un membre de la gestion."""
    require_permission(actor, "create_collaborator")
    return _add_collaborator(session, full_name, email, password, role_name)


def create_first_manager(session, full_name, email, password):
    """Crée le premier compte de gestion uniquement si aucun compte n'existe."""
    if session.scalar(select(Collaborator.id).limit(1)) is not None:
        raise PermissionError(
            "Un compte existe déjà. Passez par un membre de la gestion."
        )
    return _add_collaborator(session, full_name, email, password, "gestion")


def authenticate(session, email, password):
    """Renvoie le collaborateur identifié, ou None si les identifiants échouent."""
    user = session.scalar(
        select(Collaborator).where(Collaborator.email == normalize_email(email))
    )
    stored_hash = user.password_hash if user is not None else DUMMY_HASH
    if not verify_password(stored_hash, password) or user is None:
        return None
    if password_hasher.check_needs_rehash(user.password_hash):
        user.password_hash = password_hasher.hash(password)
        session.flush()
    return user
