"""Vérifie l'initialisation des rôles et la détection de l'ancien schéma."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from database import create_db_engine
from init_db import initialize_database
from models import Role


def test_roles_are_initialized_only_once(test_engine):
    initialize_database(test_engine)
    with Session(test_engine) as session:
        assert sorted(session.scalars(select(Role.name))) == [
            "commercial",
            "gestion",
            "support",
        ]


def test_old_schema_requires_a_migration():
    engine = create_db_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE collaborators (id INTEGER, role TEXT)"))
    with pytest.raises(ValueError, match="Ancien schéma"):
        initialize_database(engine)
    engine.dispose()
