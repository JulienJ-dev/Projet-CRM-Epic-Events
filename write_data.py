"""Création et modification des données par l'utilisateur connecté.

Les fonctions valident les données, effectuent un flush et renvoient l'objet.
L'appelant valide ou annule la transaction avec sa session SQLAlchemy.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import joinedload

import accounts
from authentication import authorize_current_user
from models import Client, Collaborator, Contract, Event
from permissions import require_permission
from validation import (
    validate_amount,
    validate_count,
    validate_date,
    validate_datetime,
    validate_email,
    validate_fields,
    validate_id,
    validate_notes,
    validate_text,
)


CLIENT_FIELDS = {
    "full_name",
    "email",
    "phone",
    "company_name",
    "created_at",
    "updated_at",
    "sales_contact_id",
}
CONTRACT_FIELDS = {"client_id", "total_amount", "amount_due", "created_at", "is_signed"}
EVENT_FIELDS = {
    "contract_id",
    "support_contact_id",
    "name",
    "start_at",
    "end_at",
    "location",
    "attendee_count",
    "notes",
}


def _get_record(session, model, record_id):
    options = [joinedload(Contract.client)] if model is Contract else []
    record = session.get(
        model, validate_id(record_id), options=options, populate_existing=True
    )
    if record is None:
        raise ValueError(f"{model.__name__} introuvable.")
    return record


def _apply_changes(session, record, values):
    for field, value in values.items():
        setattr(record, field, value)
    session.flush()
    return record


def create_collaborator(session, full_name, email, password, role_name):
    """Crée un collaborateur à la demande d'un utilisateur de la gestion."""
    with session.no_autoflush:
        actor = authorize_current_user(session, "create_collaborator")
        return accounts.create_collaborator(
            session, actor, full_name, email, password, role_name
        )


def update_collaborator(session, employee_id, **changes):
    """Modifie le nom, l'email, le mot de passe ou le département d'un compte."""
    with session.no_autoflush:
        actor = authorize_current_user(session, "update_collaborator")
        return accounts._update_collaborator(session, actor, employee_id, **changes)


def delete_collaborator(session, employee_id, replacement_sales_contact_id=None):
    """Supprime un compte en conservant ses clients et événements."""
    with session.no_autoflush:
        authorize_current_user(session, "delete_collaborator")
        user = _get_record(session, Collaborator, employee_id)
        clients = session.scalars(
            select(Client).where(Client.sales_contact_id == user.id)
        ).all()
        replacement = None
        if replacement_sales_contact_id is not None:
            replacement = _get_record(
                session, Collaborator, replacement_sales_contact_id
            )
            if replacement.id == user.id or replacement.role.name != "commercial":
                raise ValueError(
                    "Choisissez un autre collaborateur du département commercial."
                )
        if clients and replacement is None:
            raise ValueError("Indiquez un commercial de remplacement pour ses clients.")
        events = session.scalars(
            select(Event).where(Event.support_contact_id == user.id)
        ).all()
    for client in clients:
        client.sales_contact = replacement
    for current_event in events:
        current_event.support_contact = None
    session.delete(user)
    session.flush()
    return employee_id


def _client_values(values):
    values["full_name"] = validate_text(values["full_name"], "Le nom", 100)
    values["email"] = validate_email(values["email"])
    values["phone"] = validate_text(values["phone"], "Le téléphone", 30)
    values["company_name"] = validate_text(values["company_name"], "L'entreprise", 150)
    values["created_at"] = validate_date(values["created_at"])
    values["updated_at"] = validate_date(values["updated_at"])
    if values["updated_at"] < values["created_at"]:
        raise ValueError("La dernière mise à jour ne peut pas précéder la création.")
    return values


def create_client(
    session, full_name, email, phone, company_name, created_at=None, updated_at=None
):
    """Crée un client automatiquement associé au commercial connecté."""
    with session.no_autoflush:
        actor = authorize_current_user(session, "create_client")
        values = _client_values(
            {
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "company_name": company_name,
                "created_at": date.today() if created_at is None else created_at,
                "updated_at": date.today() if updated_at is None else updated_at,
            }
        )
    client = Client(**values, sales_contact=actor)
    session.add(client)
    session.flush()
    return client


def update_client(session, client_id, **changes):
    """Modifie un client du commercial connecté, sans changer son responsable."""
    with session.no_autoflush:
        actor = authorize_current_user(session, "read_client")
        client = _get_record(session, Client, client_id)
        require_permission(actor, "update_client", client)
        validate_fields(changes, CLIENT_FIELDS)
        if "sales_contact_id" in changes:
            contact_id = validate_id(changes["sales_contact_id"])
            if contact_id != actor.id:
                raise PermissionError("Vous ne pouvez pas transférer ce client.")
        values = {field: getattr(client, field) for field in CLIENT_FIELDS}
        values.update(changes)
        if "updated_at" not in changes:
            values["updated_at"] = date.today()
        values = _client_values(values)
    return _apply_changes(session, client, values)


def _contract_values(values):
    values["total_amount"] = validate_amount(values["total_amount"])
    values["amount_due"] = validate_amount(values["amount_due"])
    if values["amount_due"] > values["total_amount"]:
        raise ValueError("Le montant restant ne peut pas dépasser le montant total.")
    values["created_at"] = validate_date(values["created_at"])
    if type(values["is_signed"]) is not bool:
        raise ValueError("Le statut de signature doit être un booléen.")
    return values


def create_contract(
    session, client_id, total_amount, amount_due, is_signed=False, created_at=None
):
    """Crée un contrat pour un client existant ; réservé à la gestion."""
    with session.no_autoflush:
        authorize_current_user(session, "create_contract")
        values = _contract_values(
            {
                "total_amount": total_amount,
                "amount_due": amount_due,
                "is_signed": is_signed,
                "created_at": date.today() if created_at is None else created_at,
            }
        )
        client = _get_record(session, Client, client_id)
    contract = Contract(**values, client=client)
    session.add(contract)
    session.flush()
    return contract


def update_contract(session, contract_id, **changes):
    """Modifie tous les champs métier d'un contrat, y compris son client."""
    with session.no_autoflush:
        actor = authorize_current_user(session, "read_contract")
        contract = _get_record(session, Contract, contract_id)
        require_permission(actor, "update_contract", contract)
        validate_fields(changes, CONTRACT_FIELDS)
        values = {field: getattr(contract, field) for field in CONTRACT_FIELDS}
        values.update(changes)
        client = _get_record(session, Client, values.pop("client_id"))
        if actor.role.name == "commercial":
            require_permission(actor, "update_client", client)
        values = _contract_values(values)
        values["client"] = client
    return _apply_changes(session, contract, values)


def _event_values(values):
    values["name"] = validate_text(values["name"], "Le nom de l'événement", 150)
    values["start_at"] = validate_datetime(values["start_at"])
    values["end_at"] = validate_datetime(values["end_at"])
    if values["end_at"] <= values["start_at"]:
        raise ValueError("La fin de l'événement doit suivre son début.")
    values["location"] = validate_text(values["location"], "Le lieu", 255)
    values["attendee_count"] = validate_count(values["attendee_count"])
    values["notes"] = validate_notes(values["notes"])
    return values


def create_event(
    session, contract_id, name, start_at, end_at, location, attendee_count, notes=None
):
    """Crée un événement sans support pour un contrat signé de son client."""
    with session.no_autoflush:
        actor = authorize_current_user(session, "read_contract")
        contract = _get_record(session, Contract, contract_id)
        require_permission(actor, "create_event", contract)
        values = _event_values(
            {
                "name": name,
                "start_at": start_at,
                "end_at": end_at,
                "location": location,
                "attendee_count": attendee_count,
                "notes": notes,
            }
        )
    new_event = Event(**values, contract=contract)
    session.add(new_event)
    session.flush()
    return new_event


def update_event(session, event_id, **changes):
    """Modifie un événement affecté ; son affectation est réservée à la gestion."""
    with session.no_autoflush:
        actor = authorize_current_user(session, "read_event")
        current_event = _get_record(session, Event, event_id)
        validate_fields(changes, EVENT_FIELDS)
        if set(changes) == {"support_contact_id"}:
            require_permission(actor, "assign_support", current_event)
        else:
            require_permission(actor, "update_event", current_event)
            if "support_contact_id" in changes:
                require_permission(actor, "assign_support", current_event)
        values = {field: getattr(current_event, field) for field in EVENT_FIELDS}
        values.update(changes)
        contract = _get_record(session, Contract, values.pop("contract_id"))
        if contract.id != current_event.contract_id and not contract.is_signed:
            raise ValueError("Le nouveau contrat de l'événement doit être signé.")
        support_id = values.pop("support_contact_id")
        support = None
        if support_id is not None:
            support = _get_record(session, Collaborator, support_id)
            if support.role.name != "support":
                raise ValueError("Le contact doit appartenir au département support.")
        values = _event_values(values)
        values["contract"] = contract
        values["support_contact"] = support
    return _apply_changes(session, current_event, values)


def assign_support(session, event_id, support_contact_id):
    """Affecte, remplace ou retire le support d'un événement ; réservé à la gestion."""
    return update_event(session, event_id, support_contact_id=support_contact_id)
