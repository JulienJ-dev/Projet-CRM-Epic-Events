"""Point d'entrée de l'interface en ligne de commande du CRM."""

from getpass import getpass

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from authentication import AuthenticationError, get_current_user, login, logout
from cli_commands import execute
from cli_parser import build_parser
from database import engine
from views import show_message


def main(argv=None):
    args = build_parser().parse_args(argv)

    try:
        if args.command == "logout":
            logout()
            show_message("Déconnexion effectuée.")
            return 0
        with Session(engine) as session, session.begin():
            if args.command == "login":
                email = input("Adresse email : ")
                password = getpass("Mot de passe : ")
                user = login(session, email, password)
                message = f"Connecté : {user.full_name}. Session valable 8 heures."
            elif args.command == "whoami":
                user = get_current_user(session)
                message = (
                    f"Employé {user.id} : {user.full_name}\n"
                    f"Email : {user.email}\nDépartement : {user.role.name}"
                )
            else:
                message = execute(session, args, getpass)
        if message:
            show_message(message)
        return 0
    except (AuthenticationError, PermissionError, ValueError, OSError) as error:
        show_message(str(error), error=True)
        return 1
    except SQLAlchemyError:
        show_message(
            "Erreur de base de données. Vérifiez la configuration et init_db.py.",
            error=True,
        )
        return 1
    except (EOFError, KeyboardInterrupt):
        show_message("Commande annulée.", error=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
