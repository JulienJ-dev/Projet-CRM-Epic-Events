"""Connexion à la base de données du CRM."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, text


load_dotenv(Path(__file__).parent / ".env")


def create_db_engine(url):
    """Crée un moteur SQLAlchemy avec les clés étrangères actives pour SQLite."""
    new_engine = create_engine(url)
    if new_engine.dialect.name == "sqlite":
        event.listen(new_engine, "connect", enable_foreign_keys)
    return new_engine


def enable_foreign_keys(dbapi_connection, connection_record):
    """Active la vérification des clés étrangères sur une connexion SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL est manquante. Copiez .env.example vers .env.")

engine = create_db_engine(database_url)


if __name__ == "__main__":
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    print("Connexion à la base de données réussie.")
