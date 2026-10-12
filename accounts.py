"""Création des comptes et authentification des collaborateurs."""

import secrets

from sqlalchemy import select

from models import Collaborator, Role
from permissions import require_permission
from security import hash_password, password_hasher, verify_password
from validation import validate_email, validate_fields, validate_id, validate_text


# Permet aussi de vérifier un hash quand l'adresse email n'existe pas.
DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(32))


def normalize_email(email):
    """Normalise l'identifiant utilisé à la création et à la connexion."""
    return email.strip().lower()


def _validate_details(session, full_name, email, role_name, employee_id=None):
    full_name = validate_text(full_name, "Le nom", 100)
    email = validate_email(email)
    existing = session.scalar(select(Collaborator).where(Collaborator.email == email))
    if existing is not None and existing.id != employee_id:
        raise ValueError("Cette adresse email est déjà utilisée.")
    if role_name not in ("gestion", "commercial", "support"):
        raise ValueError("Département inconnu.")
    role = session.scalar(select(Role).where(Role.name == role_name))
    if role is None:
        raise ValueError("Département inconnu. Initialisez les rôles avec init_db.py.")
    return full_name, email, role


def _add_collaborator(session, full_name, email, password, role_name):
    full_name, email, role = _validate_details(session, full_name, email, role_name)
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


def _update_collaborator(session, actor, employee_id, **changes):
    """Modifie un compte après contrôle de l'auteur par le service d'écriture."""
    require_permission(actor, "update_collaborator")
    validate_fields(changes, {"full_name", "email", "password", "role_name"})
    user = session.get(Collaborator, validate_id(employee_id), populate_existing=True)
    if user is None:
        raise ValueError("Collaborateur introuvable.")
    full_name, email, role = _validate_details(
        session,
        changes.get("full_name", user.full_name),
        changes.get("email", user.email),
        changes.get("role_name", user.role.name),
        user.id,
    )
    password_hash = (
        hash_password(changes["password"])
        if "password" in changes
        else user.password_hash
    )
    user.full_name = full_name
    user.email = email
    user.role = role
    user.password_hash = password_hash
    session.flush()
    return user


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
