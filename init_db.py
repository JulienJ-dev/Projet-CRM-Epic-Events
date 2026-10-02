"""Crée les tables de la base de données si elles n'existent pas."""

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from database import engine
from models import Base, Role


DEFAULT_ROLES = ("gestion", "commercial", "support")


def initialize_database(db_engine):
    """Crée les tables et les trois rôles sans dupliquer les données."""
    inspector = inspect(db_engine)
    if "collaborators" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("collaborators")}
        if "role_id" not in columns:
            raise ValueError(
                "Ancien schéma détecté : migrez la base avant de continuer."
            )

    Base.metadata.create_all(db_engine)
    with Session(db_engine) as session, session.begin():
        existing_roles = set(session.scalars(select(Role.name)))
        for name in DEFAULT_ROLES:
            if name not in existing_roles:
                session.add(Role(name=name))


if __name__ == "__main__":
    initialize_database(engine)
    print("Tables et rôles du CRM créés ou déjà présents.")
