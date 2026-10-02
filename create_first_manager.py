"""Outil d'installation pour créer le premier compte de gestion."""

from getpass import getpass

from sqlalchemy import select
from sqlalchemy.orm import Session

from accounts import create_first_manager
from database import engine
from models import Collaborator


def main():
    with Session(engine) as session, session.begin():
        if session.scalar(select(Collaborator.id).limit(1)) is not None:
            raise PermissionError(
                "Un compte existe déjà. Utilisez un compte de gestion."
            )
        full_name = input("Nom complet : ")
        email = input("Adresse email : ")
        password = getpass("Mot de passe : ")
        if password != getpass("Confirmez le mot de passe : "):
            raise ValueError("Les mots de passe ne correspondent pas.")
        user = create_first_manager(session, full_name, email, password)
        employee_id = user.id
    print(f"Compte de gestion créé. Numéro d'employé : {employee_id}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, PermissionError) as error:
        print(error)
        raise SystemExit(1)
