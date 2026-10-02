"""Bases et comptes de test isolés de la base locale."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import create_db_engine
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
