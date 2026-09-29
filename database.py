"""Connexion à la base de données du CRM."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


load_dotenv(Path(__file__).parent / ".env")

database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL est manquante. Copiez .env.example vers .env.")

engine = create_engine(database_url)


if __name__ == "__main__":
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    print("Connexion à la base de données réussie.")
