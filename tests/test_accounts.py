"""Vérifie la création sécurisée et l'identification des comptes."""

import pytest
from argon2 import PasswordHasher
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from accounts import authenticate, create_collaborator, create_first_manager
from models import Collaborator
from security import hash_password, password_hasher, verify_password


PASSWORD = "Mot de passe de test 2026"


def test_password_hashes_have_different_salts():
    first_hash = hash_password(PASSWORD)
    second_hash = hash_password(PASSWORD)
    assert first_hash != second_hash
    assert first_hash.startswith("$argon2id$")
    assert PASSWORD not in first_hash
    assert verify_password(first_hash, PASSWORD)
    assert not verify_password(first_hash, "autre mot de passe")
    assert not verify_password("hash invalide", PASSWORD)
    assert not verify_password(first_hash, None)
    assert not verify_password(first_hash, "a" * 129)


def test_first_manager_and_authentication(session):
    manager = create_first_manager(session, " Dawn ", " DAWN@example.test ", PASSWORD)
    session.commit()
    session.expire_all()
    assert manager.id is not None
    assert manager.full_name == "Dawn"
    assert manager.email == "dawn@example.test"
    assert manager.role.name == "gestion"
    assert manager.password_hash != PASSWORD
    assert authenticate(session, " DAWN@example.test ", PASSWORD) is manager
    assert authenticate(session, manager.email, "mauvais mot de passe") is None
    assert authenticate(session, "inconnu@example.test", PASSWORD) is None
    assert authenticate(session, "' OR 1=1 --", PASSWORD) is None


def test_only_management_can_create_accounts(session):
    manager = create_first_manager(session, "Dawn", "dawn@example.test", PASSWORD)
    commercial = create_collaborator(
        session, manager, "Bill", "bill@example.test", PASSWORD, "commercial"
    )
    assert commercial.role.name == "commercial"
    assert commercial.password_hash != manager.password_hash
    assert verify_password(commercial.password_hash, PASSWORD)


@pytest.mark.parametrize("actor_name", ["commercial", "support", None])
def test_unauthorized_creation_does_not_add_a_user(session, users, actor_name):
    actor = users[actor_name] if actor_name else None
    count_before = session.scalar(select(func.count()).select_from(Collaborator))
    with pytest.raises(PermissionError):
        create_collaborator(
            session, actor, "New user", "new@example.test", PASSWORD, "gestion"
        )
    assert (
        session.scalar(select(func.count()).select_from(Collaborator)) == count_before
    )


def test_bootstrap_cannot_be_reused(session, users):
    with pytest.raises(PermissionError):
        create_first_manager(session, "Dawn", "dawn@example.test", PASSWORD)


@pytest.mark.parametrize(
    "field, value",
    [
        ("full_name", " "),
        ("full_name", "a" * 101),
        ("email", "adresse invalide"),
        ("email", "a" * 250 + "@example.test"),
        ("password", "court"),
        ("password", "a" * 129),
        ("password", " " * 12),
        ("password", None),
        ("role_name", "administrateur"),
    ],
)
def test_invalid_account_is_rejected(session, users, field, value):
    details = dict(
        full_name="Bill",
        email="bill@example.test",
        password=PASSWORD,
        role_name="commercial",
    )
    details[field] = value
    with pytest.raises(ValueError):
        create_collaborator(session, users["gestion"], **details)


def test_duplicate_email_is_rejected_after_normalization(session):
    manager = create_first_manager(session, "Dawn", "dawn@example.test", PASSWORD)
    with pytest.raises(ValueError):
        create_collaborator(
            session, manager, "Autre compte", " DAWN@example.test ", PASSWORD, "support"
        )


def test_hash_is_updated_when_parameters_change(session):
    manager = create_first_manager(session, "Dawn", "dawn@example.test", PASSWORD)
    old_hash = PasswordHasher(time_cost=1, memory_cost=8192).hash(PASSWORD)
    manager.password_hash = old_hash
    session.commit()
    assert authenticate(session, manager.email, PASSWORD) is manager
    session.commit()
    session.expire_all()
    assert manager.password_hash != old_hash
    assert not password_hasher.check_needs_rehash(manager.password_hash)


def test_account_requires_an_existing_role(session):
    session.add(
        Collaborator(
            full_name="Bill",
            email="bill@example.test",
            password_hash="test",
            role_id=999,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
