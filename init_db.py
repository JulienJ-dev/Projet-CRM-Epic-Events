"""Crée les tables de la base de données si elles n'existent pas."""

from database import engine
from models import Base


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    print("Tables du CRM créées ou déjà présentes.")
