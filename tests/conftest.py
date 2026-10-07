"""Bases et comptes de test isolés de la base locale."""

import secrets

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import create_db_engine
from accounts import create_first_manager
from init_db import initialize_database
from models import Client, Collaborator, Role


@pytest.fixture
def test_engine():
    engine = create_db_engine("sqlite:///:memory:")
    initialize_database(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(test_engine):
    with Session(test_engine) as db_session:
        yield db_session


@pytest.fixture
def users(session):
    users = {}
    roles = {role.name: role for role in session.scalars(select(Role))}
    for name in ("gestion", "commercial", "support", "other_commercial"):
        role_name = "commercial" if name == "other_commercial" else name
        users[name] = Collaborator(
            full_name=name,
            email=f"{name}@example.test",
            password_hash="hash de test non utilisable pour une connexion",
            role=roles[role_name],
        )
    session.add_all(users.values())
    session.flush()
    return users


@pytest.fixture
def client(session, users):
    client = Client(
        full_name="Client test",
        email="client@example.test",
        phone="123456789",
        company_name="Entreprise test",
        sales_contact=users["commercial"],
    )
    session.add(client)
    session.flush()
    return client


@pytest.fixture
def auth_config(monkeypatch, tmp_path):
    token_file = tmp_path / ".session_token"
    monkeypatch.setenv("JWT_SECRET_KEY", secrets.token_urlsafe(48))
    monkeypatch.setenv("SESSION_TOKEN_FILE", str(token_file))
    return token_file


@pytest.fixture
def manager(session):
    manager = create_first_manager(
        session, "Dawn", "dawn@example.test", "Mot de passe de test 2026"
    )
    session.commit()
    return manager
