"""Affichage des données du CRM dans le terminal, sans requêtes SQL."""

import sys

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text


def _text(value):
    value = "Non attribué" if value is None else str(value)
    # Affiche les balises littéralement et retire les contrôles du terminal.
    value = "".join(char for char in value if char.isprintable() or char in "\n\t")
    return Text(value)


def show_message(message, error=False):
    console = Console(file=sys.stderr if error else sys.stdout, highlight=False)
    console.print(_text(message), style="red" if error else "green", soft_wrap=True)


def _table(title, columns, rows):
    console = Console(highlight=False)
    if not rows:
        console.print(_text(title))
        console.print("Aucun résultat.")
        return
    table = Table(
        *columns, title=title, box=box.ASCII, header_style="bold cyan", show_lines=True
    )
    for row in rows:
        table.add_row(*[_text(value) for value in row])
    console.print(table)


def contact(user):
    return None if user is None else f"{user.id} - {user.full_name}"


def show_clients(clients):
    _table(
        "Clients",
        ["ID", "Contact", "Entreprise", "Commercial"],
        [
            (
                client.id,
                client.full_name,
                client.company_name,
                contact(client.sales_contact),
            )
            for client in clients
        ],
    )


def show_contracts(contracts):
    _table(
        "Contrats",
        ["ID", "Client", "Total", "Restant", "Signé"],
        [
            (
                contract.id,
                contract.client.full_name,
                f"{contract.total_amount:.2f}",
                f"{contract.amount_due:.2f}",
                "Oui" if contract.is_signed else "Non",
            )
            for contract in contracts
        ],
    )


def show_events(events):
    _table(
        "Événements",
        ["ID", "Nom", "Début", "Support"],
        [
            (
                current.id,
                current.name,
                current.start_at.strftime("%Y-%m-%d %H:%M"),
                contact(current.support_contact),
            )
            for current in events
        ],
    )


def show_collaborators(users):
    _table(
        "Collaborateurs",
        ["ID", "Nom", "Email", "Département"],
        [(user.id, user.full_name, user.email, user.role.name) for user in users],
    )


def show_client(client):
    _table(
        "Détail du client",
        ["Champ", "Valeur"],
        [
            ("ID", client.id),
            ("Nom", client.full_name),
            ("Email", client.email),
            ("Téléphone", client.phone),
            ("Entreprise", client.company_name),
            ("Création", client.created_at),
            ("Dernier contact", client.updated_at),
            ("Commercial", contact(client.sales_contact)),
        ],
    )


def show_contract(contract):
    _table(
        "Détail du contrat",
        ["Champ", "Valeur"],
        [
            ("ID", contract.id),
            ("Client ID", contract.client_id),
            ("Client", contract.client.full_name),
            ("Email client", contract.client.email),
            ("Téléphone client", contract.client.phone),
            ("Commercial", contact(contract.client.sales_contact)),
            ("Total", f"{contract.total_amount:.2f}"),
            ("Restant", f"{contract.amount_due:.2f}"),
            ("Création", contract.created_at),
            ("Signé", "Oui" if contract.is_signed else "Non"),
        ],
    )


def show_event(current):
    client = current.contract.client
    _table(
        "Détail de l'événement",
        ["Champ", "Valeur"],
        [
            ("ID", current.id),
            ("Nom", current.name),
            ("Contrat ID", current.contract_id),
            ("Client ID", client.id),
            ("Client", client.full_name),
            ("Email client", client.email),
            ("Téléphone client", client.phone),
            ("Commercial", contact(client.sales_contact)),
            ("Support", contact(current.support_contact)),
            ("Début", current.start_at.strftime("%Y-%m-%d %H:%M")),
            ("Fin", current.end_at.strftime("%Y-%m-%d %H:%M")),
            ("Lieu", current.location),
            ("Participants", current.attendee_count),
            ("Notes", current.notes or ""),
        ],
    )


def show_collaborator(user):
    _table(
        "Détail du collaborateur",
        ["Champ", "Valeur"],
        [
            ("Numéro d'employé", user.id),
            ("Nom", user.full_name),
            ("Email", user.email),
            ("Département", user.role.name),
        ],
    )
