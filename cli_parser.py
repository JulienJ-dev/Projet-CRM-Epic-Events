"""Définition des commandes et conversion des arguments du terminal."""

import argparse
from datetime import date, datetime

from validation import validate_amount, validate_count, validate_id


def positive_id(value):
    try:
        return validate_id(int(value))
    except ValueError:
        raise argparse.ArgumentTypeError(
            "L'identifiant doit être un entier positif."
        ) from None


def attendee_count(value):
    try:
        return validate_count(int(value))
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from None


def amount(value):
    try:
        return validate_amount(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from None


def date_value(value):
    try:
        result = date.fromisoformat(value)
        if result.isoformat() != value:
            raise ValueError()
        return result
    except ValueError:
        raise argparse.ArgumentTypeError(
            "Utilisez une date au format AAAA-MM-JJ."
        ) from None


def datetime_value(value):
    try:
        result = datetime.strptime(value, "%Y-%m-%d %H:%M")
        if result.strftime("%Y-%m-%d %H:%M") != value:
            raise ValueError()
        return result
    except ValueError:
        raise argparse.ArgumentTypeError(
            "Utilisez le format 'AAAA-MM-JJ HH:MM'."
        ) from None


def _entity_commands(commands, name, help_text):
    group = commands.add_parser(name, help=help_text)
    actions = group.add_subparsers(dest="action", required=True)
    listing = actions.add_parser("list", help="Afficher la liste")
    showing = actions.add_parser("show", help="Afficher toutes les informations")
    showing.add_argument("record_id", type=positive_id, help="Identifiant")
    return actions, listing


def _add_collaborators(commands):
    actions, listing = _entity_commands(
        commands, "collaborators", "Gérer les collaborateurs (gestion)"
    )
    for action in ("create", "update"):
        parser = actions.add_parser(
            action,
            help="Créer un compte" if action == "create" else "Modifier un compte",
        )
        creating = action == "create"
        if not creating:
            parser.add_argument("record_id", type=positive_id)
            parser.add_argument(
                "--change-password",
                action="store_true",
                help="Saisir un nouveau mot de passe masqué",
            )
        parser.add_argument(
            "--name", dest="full_name", required=creating, help="Nom complet"
        )
        parser.add_argument("--email", required=creating, help="Adresse email")
        parser.add_argument(
            "--department",
            dest="role_name",
            required=creating,
            choices=("gestion", "commercial", "support"),
        )
    deletion = actions.add_parser(
        "delete", help="Supprimer un compte après confirmation"
    )
    deletion.add_argument("record_id", type=positive_id)
    deletion.add_argument(
        "--replacement-commercial",
        type=positive_id,
        help="Commercial qui reprend les clients éventuels",
    )


def _add_clients(commands):
    actions, listing = _entity_commands(
        commands, "clients", "Consulter et gérer les clients"
    )
    for action in ("create", "update"):
        parser = actions.add_parser(
            action,
            help="Créer un client" if action == "create" else "Modifier son client",
        )
        creating = action == "create"
        if not creating:
            parser.add_argument("record_id", type=positive_id)
        parser.add_argument(
            "--name", dest="full_name", required=creating, help="Nom complet du contact"
        )
        parser.add_argument("--email", required=creating)
        parser.add_argument("--phone", required=creating)
        parser.add_argument("--company", dest="company_name", required=creating)
        parser.add_argument("--created-at", type=date_value, help="AAAA-MM-JJ")
        parser.add_argument("--updated-at", type=date_value, help="AAAA-MM-JJ")


def _add_contracts(commands):
    actions, listing = _entity_commands(
        commands, "contracts", "Consulter et gérer les contrats"
    )
    listing.add_argument("--unsigned", action="store_true", help="Contrats non signés")
    listing.add_argument(
        "--unpaid", action="store_true", help="Contrats avec un restant à payer"
    )
    for action in ("create", "update"):
        parser = actions.add_parser(
            action,
            help="Créer un contrat" if action == "create" else "Modifier un contrat",
        )
        creating = action == "create"
        if not creating:
            parser.add_argument("record_id", type=positive_id)
            status = parser.add_mutually_exclusive_group()
            status.add_argument(
                "--signed", dest="is_signed", action="store_const", const=True
            )
            status.add_argument(
                "--unsigned", dest="is_signed", action="store_const", const=False
            )
        else:
            parser.add_argument("--signed", dest="is_signed", action="store_true")
        parser.add_argument("--client-id", type=positive_id, required=creating)
        parser.add_argument(
            "--total", dest="total_amount", type=amount, required=creating
        )
        parser.add_argument("--due", dest="amount_due", type=amount, required=creating)
        parser.add_argument("--created-at", type=date_value, help="AAAA-MM-JJ")


def _add_events(commands):
    actions, listing = _entity_commands(
        commands, "events", "Consulter et gérer les événements"
    )
    filters = listing.add_mutually_exclusive_group()
    filters.add_argument(
        "--unassigned", action="store_true", help="Événements sans support"
    )
    filters.add_argument(
        "--mine", action="store_true", help="Vos événements affectés (support)"
    )
    for action in ("create", "update"):
        parser = actions.add_parser(
            action,
            help=(
                "Créer un événement" if action == "create" else "Modifier son événement"
            ),
        )
        creating = action == "create"
        if not creating:
            parser.add_argument("record_id", type=positive_id)
        parser.add_argument("--contract-id", type=positive_id, required=creating)
        parser.add_argument("--name", required=creating)
        parser.add_argument(
            "--start",
            dest="start_at",
            type=datetime_value,
            required=creating,
            help="'AAAA-MM-JJ HH:MM'",
        )
        parser.add_argument(
            "--end",
            dest="end_at",
            type=datetime_value,
            required=creating,
            help="'AAAA-MM-JJ HH:MM'",
        )
        parser.add_argument("--location", required=creating)
        parser.add_argument(
            "--attendees", dest="attendee_count", type=attendee_count, required=creating
        )
        notes = parser.add_mutually_exclusive_group()
        notes.add_argument("--notes")
        if not creating:
            notes.add_argument("--clear-notes", action="store_true")
    assignment = actions.add_parser(
        "assign", help="Affecter ou retirer le support (gestion)"
    )
    assignment.add_argument("record_id", type=positive_id)
    support = assignment.add_mutually_exclusive_group(required=True)
    support.add_argument("--support-id", type=positive_id)
    support.add_argument("--clear", action="store_true", help="Retirer l'affectation")


def build_parser():
    parser = argparse.ArgumentParser(description="CRM Epic Events")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("login", help="Se connecter")
    commands.add_parser("logout", help="Se déconnecter")
    commands.add_parser("whoami", help="Afficher le compte connecté")
    _add_collaborators(commands)
    _add_clients(commands)
    _add_contracts(commands)
    _add_events(commands)
    return parser
