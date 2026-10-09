"""Lecture des données métier après authentification et autorisation."""

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from authentication import authorize_current_user
from models import Client, Contract, Event


def get_all_clients(session):
    """Renvoie tous les clients, avec leur contact commercial, triés par ID."""
    authorize_current_user(session, "read_client")
    query = select(Client).options(joinedload(Client.sales_contact)).order_by(Client.id)
    return session.scalars(query).all()


def get_all_contracts(session):
    """Renvoie tous les contrats, avec leur client et son commercial."""
    authorize_current_user(session, "read_contract")
    query = (
        select(Contract)
        .options(joinedload(Contract.client).joinedload(Client.sales_contact))
        .order_by(Contract.id)
    )
    return session.scalars(query).all()


def get_all_events(session):
    """Renvoie tous les événements, avec leur contrat, client et contacts."""
    authorize_current_user(session, "read_event")
    query = (
        select(Event)
        .options(
            joinedload(Event.contract)
            .joinedload(Contract.client)
            .joinedload(Client.sales_contact),
            joinedload(Event.support_contact),
        )
        .order_by(Event.id)
    )
    return session.scalars(query).all()
