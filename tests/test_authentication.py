"""Vérifie la session persistante et les refus des jetons non valides."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

import authentication
from authentication import (
    AuthenticationError,
    authorize_current_user,
    create_token,
    credential_fingerprint,
    decode_token,
    get_current_user,
    get_token_file,
    login,
    logout,
    save_token,
)
from models import Role
from accounts import create_first_manager
from security import hash_password


PASSWORD = "Mot de passe de test 2026"


@pytest.fixture
def payload(manager, auth_config):
    now = datetime.now(timezone.utc)
    return {
        "sub": str(manager.id),
        "iat": now,
        "exp": now + timedelta(hours=8),
        "iss": "epic-events",
        "aud": "epic-events-cli",
        "credential": credential_fingerprint(manager),
    }


def sign(payload):
    return jwt.encode(payload, os.environ["JWT_SECRET_KEY"], algorithm="HS256")


def test_login_persists_between_database_sessions(
    session, test_engine, manager, auth_config
):
    assert login(session, manager.email, PASSWORD).id == manager.id
    token = auth_config.read_text(encoding="utf-8")
    assert decode_token(token)["sub"] == str(manager.id)
    assert PASSWORD not in token
    with Session(test_engine) as other_session:
        current = get_current_user(other_session)
        assert current.id == manager.id
        assert current.role.name == "gestion"
    logout()
    logout()
    assert not auth_config.exists()
    with pytest.raises(AuthenticationError, match="Connectez-vous"):
        get_current_user(session)


def test_invalid_credentials_do_not_replace_the_session(session, manager, auth_config):
    login(session, manager.email, PASSWORD)
    original_token = auth_config.read_bytes()
    with pytest.raises(AuthenticationError, match="incorrect"):
        login(session, manager.email, "mauvais mot de passe")
    assert auth_config.read_bytes() == original_token


def test_expired_token_requires_a_new_login(session, payload, auth_config):
    payload["iat"] = datetime.now(timezone.utc) - timedelta(hours=9)
    payload["exp"] = datetime.now(timezone.utc) - timedelta(hours=1)
    save_token(sign(payload))
    with pytest.raises(AuthenticationError, match="expirée"):
        get_current_user(session)
    assert not auth_config.exists()


@pytest.mark.parametrize("claim", ["sub", "exp", "iat", "iss", "aud", "credential"])
def test_required_claims_cannot_be_omitted(payload, claim, auth_config):
    del payload[claim]
    with pytest.raises(AuthenticationError):
        decode_token(sign(payload))


@pytest.mark.parametrize(
    "claim, value",
    [
        ("sub", "inconnu"),
        ("sub", "-1"),
        ("sub", "0"),
        ("sub", "01"),
        ("sub", None),
        ("exp", None),
        ("exp", "jamais"),
        ("iat", None),
        ("iss", "autre-application"),
        ("aud", "autre-application"),
        ("credential", None),
        ("credential", "é" * 64),
        ("credential", "court"),
    ],
)
def test_malformed_claims_are_rejected(payload, claim, value, auth_config):
    payload[claim] = value
    with pytest.raises(AuthenticationError):
        decode_token(sign(payload))


def test_future_issue_date_is_rejected(payload, auth_config):
    payload["iat"] = datetime.now(timezone.utc) + timedelta(hours=1)
    with pytest.raises(AuthenticationError):
        decode_token(sign(payload))


def test_tampered_signature_is_rejected(session, manager, auth_config):
    parts = create_token(manager).split(".")
    replacement = "A" if parts[2][0] != "A" else "B"
    parts[2] = replacement + parts[2][1:]
    save_token(".".join(parts))
    with pytest.raises(AuthenticationError):
        get_current_user(session)
    assert not auth_config.exists()


@pytest.mark.parametrize("algorithm", ["none", "HS512"])
def test_only_hs256_is_accepted(payload, algorithm, auth_config):
    key = None if algorithm == "none" else os.environ["JWT_SECRET_KEY"]
    token = jwt.encode(payload, key, algorithm=algorithm)
    with pytest.raises(AuthenticationError):
        decode_token(token)


def test_wrong_signing_key_is_rejected(payload, auth_config):
    token = jwt.encode(
        payload, "autre-cle-de-test-qui-fait-plus-de-32-octets", algorithm="HS256"
    )
    with pytest.raises(AuthenticationError):
        decode_token(token)


def test_current_permissions_follow_the_database(
    session, test_engine, manager, auth_config
):
    login(session, manager.email, PASSWORD)
    assert authorize_current_user(session, "create_collaborator").id == manager.id
    with Session(test_engine) as other_session, other_session.begin():
        other_manager = other_session.get(type(manager), manager.id)
        other_manager.role = other_session.scalar(
            select(Role).where(Role.name == "support")
        )
    with pytest.raises(PermissionError):
        authorize_current_user(session, "create_collaborator")
    assert authorize_current_user(session, "read_client").role.name == "support"


def test_role_claim_is_not_used_as_an_authorization(
    session, manager, payload, auth_config
):
    manager.role = session.scalar(select(Role).where(Role.name == "support"))
    session.commit()
    payload["role"] = "gestion"
    save_token(sign(payload))
    with pytest.raises(PermissionError):
        authorize_current_user(session, "create_collaborator")


def test_deleted_account_cannot_use_its_token(session, manager, auth_config):
    login(session, manager.email, PASSWORD)
    session.delete(manager)
    session.commit()
    with pytest.raises(AuthenticationError, match="n'existe plus"):
        get_current_user(session)
    assert not auth_config.exists()


def test_password_change_invalidates_the_token(session, manager, auth_config):
    login(session, manager.email, PASSWORD)
    manager.password_hash = hash_password("Autre mot de passe de test 2026")
    session.commit()
    with pytest.raises(AuthenticationError, match="modifiés"):
        get_current_user(session)
    assert not auth_config.exists()


def test_recreated_account_cannot_reuse_the_old_token(session, manager, auth_config):
    login(session, manager.email, PASSWORD)
    old_id = manager.id
    session.delete(manager)
    session.commit()
    new_manager = create_first_manager(
        session, "Autre compte", "autre@example.test", PASSWORD
    )
    session.commit()
    assert new_manager.id == old_id
    with pytest.raises(AuthenticationError, match="modifiés"):
        get_current_user(session)
    assert not auth_config.exists()


def test_corrupted_file_is_removed(session, auth_config):
    auth_config.write_bytes(b"\xff\xfe")
    with pytest.raises(AuthenticationError, match="illisible"):
        get_current_user(session)
    assert not auth_config.exists()


@pytest.mark.parametrize("secret", ["", "trop-court", " " * 32])
def test_missing_or_short_secret_preserves_the_token(
    session, manager, auth_config, monkeypatch, secret
):
    login(session, manager.email, PASSWORD)
    original_token = auth_config.read_bytes()
    monkeypatch.setenv("JWT_SECRET_KEY", secret)
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        get_current_user(session)
    assert auth_config.read_bytes() == original_token


def test_token_write_failure_preserves_the_previous_session(auth_config, monkeypatch):
    save_token("ancien jeton")

    def fail_replace(source, target):
        raise OSError("Écriture impossible")

    monkeypatch.setattr(authentication.os, "replace", fail_replace)
    with pytest.raises(OSError):
        save_token("nouveau jeton")
    assert auth_config.read_text(encoding="utf-8") == "ancien jeton"
    assert list(auth_config.parent.iterdir()) == [auth_config]


def test_default_token_file_stays_in_the_project(monkeypatch):
    monkeypatch.delenv("SESSION_TOKEN_FILE", raising=False)
    assert get_token_file() == Path(authentication.__file__).with_name(".session_token")


def test_relative_token_file_is_resolved_from_the_project(monkeypatch):
    monkeypatch.setenv("SESSION_TOKEN_FILE", ".session_token")
    assert get_token_file() == Path(authentication.__file__).with_name(".session_token")
