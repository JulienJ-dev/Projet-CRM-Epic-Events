"""Connexion à la base de données du CRM."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, text


load_dotenv(Path(__file__).parent / ".env")

database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL est manquante. Copiez .env.example vers .env.")

engine = create_engine(database_url)


if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


if __name__ == "__main__":
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    print("Connexion à la base de données réussie.")
