"""Lecture des données métier après authentification et autorisation."""

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from authentication import authorize_current_user
from models import Client, Collaborator, Contract, Event
from validation import validate_id


CLIENT_RELATIONS = [joinedload(Client.sales_contact)]
CONTRACT_RELATIONS = [joinedload(Contract.client).joinedload(Client.sales_contact)]
EVENT_RELATIONS = [
    joinedload(Event.contract)
    .joinedload(Contract.client)
    .joinedload(Client.sales_contact),
    joinedload(Event.support_contact),
]


def _get_by_id(session, model, record_id, action, relations):
    authorize_current_user(session, action)
    record = session.scalar(
        select(model)
        .where(model.id == validate_id(record_id))
        .options(*relations)
        .execution_options(populate_existing=True)
    )
    if record is None:
        raise ValueError(f"{model.__name__} introuvable.")
    return record


def get_client(session, client_id):
    return _get_by_id(session, Client, client_id, "read_client", CLIENT_RELATIONS)


def get_contract(session, contract_id):
    return _get_by_id(
        session, Contract, contract_id, "read_contract", CONTRACT_RELATIONS
    )


def get_event(session, event_id):
    return _get_by_id(session, Event, event_id, "read_event", EVENT_RELATIONS)


def get_collaborator(session, employee_id):
    return _get_by_id(
        session,
        Collaborator,
        employee_id,
        "read_collaborator",
        [joinedload(Collaborator.role)],
    )


def get_all_collaborators(session):
    """Réserve la consultation des comptes à la gestion."""
    authorize_current_user(session, "read_collaborator")
    return session.scalars(
        select(Collaborator)
        .options(joinedload(Collaborator.role))
        .order_by(Collaborator.id)
    ).all()


def get_all_clients(session):
    """Renvoie tous les clients, avec leur contact commercial, triés par ID."""
    authorize_current_user(session, "read_client")
    query = select(Client).options(*CLIENT_RELATIONS).order_by(Client.id)
    return session.scalars(query).all()


def get_all_contracts(session, unsigned=False, unpaid=False):
    """Renvoie tous les contrats, avec leur client et son commercial."""
    authorize_current_user(session, "read_contract")
    if type(unsigned) is not bool or type(unpaid) is not bool:
        raise ValueError("Les filtres doivent être des booléens.")
    query = select(Contract).options(*CONTRACT_RELATIONS).order_by(Contract.id)
    if unsigned:
        query = query.where(Contract.is_signed.is_(False))
    if unpaid:
        query = query.where(Contract.amount_due > 0)
    return session.scalars(query).all()


def get_all_events(session, unassigned=False, mine=False):
    """Renvoie tous les événements, avec leur contrat, client et contacts."""
    user = authorize_current_user(session, "read_event")
    if type(unassigned) is not bool or type(mine) is not bool:
        raise ValueError("Les filtres doivent être des booléens.")
    if unassigned and mine:
        raise ValueError("Choisissez les événements sans support ou vos événements.")
    if mine and user.role.name != "support":
        raise PermissionError("Le filtre de vos événements est réservé au support.")
    query = select(Event).options(*EVENT_RELATIONS).order_by(Event.id)
    if unassigned:
        query = query.where(Event.support_contact_id.is_(None))
    if mine:
        query = query.where(Event.support_contact_id == user.id)
    return session.scalars(query).all()
