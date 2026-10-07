"""Commandes de connexion, de déconnexion et d'identification du CRM."""

import argparse
import sys
from getpass import getpass

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from authentication import AuthenticationError, get_current_user, login, logout
from database import engine


def main(argv=None):
    parser = argparse.ArgumentParser(description="Connexion au CRM Epic Events")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("login", help="Se connecter avec son email et son mot de passe")
    commands.add_parser("logout", help="Supprimer la session locale")
    commands.add_parser("whoami", help="Afficher le compte actuellement connecté")
    args = parser.parse_args(argv)

    try:
        if args.command == "logout":
            logout()
            print("Déconnexion effectuée.")
            return 0
        with Session(engine) as session, session.begin():
            if args.command == "login":
                email = input("Adresse email : ")
                password = getpass("Mot de passe : ")
                user = login(session, email, password)
                message = f"Connecté : {user.full_name}. Session valable 8 heures."
            else:
                user = get_current_user(session)
                message = (
                    f"Employé {user.id} : {user.full_name}\n"
                    f"Email : {user.email}\nDépartement : {user.role.name}"
                )
        print(message)
        return 0
    except (AuthenticationError, PermissionError, ValueError, OSError) as error:
        print(error, file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print(
            "Erreur de base de données. Vérifiez la configuration et init_db.py.",
            file=sys.stderr,
        )
        return 1
    except (EOFError, KeyboardInterrupt):
        print("Connexion annulée.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
