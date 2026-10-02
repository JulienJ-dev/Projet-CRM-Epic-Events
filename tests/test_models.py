"""Vérifie les relations et les contraintes de la base de données."""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from models import Client, Collaborator, Contract, Event, Role


def create_client(session):
    commercial = Collaborator(
        full_name="Commercial test",
        email="commercial@example.test",
        password_hash="test",
        role=session.scalar(select(Role).where(Role.name == "commercial")),
    )
    client = Client(
        full_name="Client test",
        email="client@example.test",
        phone="123456789",
        company_name="Entreprise test",
        sales_contact=commercial,
    )
    session.add(client)
    session.flush()
    return client


def test_relations_between_client_contract_and_event(session):
    client = create_client(session)
    support = Collaborator(
        full_name="Support test",
        email="support@example.test",
        password_hash="test",
        role=session.scalar(select(Role).where(Role.name == "support")),
    )
    contract = Contract(
        client=client,
        total_amount=Decimal("100.00"),
        amount_due=Decimal("25.00"),
        is_signed=True,
    )
    event = Event(
        contract=contract,
        support_contact=support,
        name="Événement test",
        start_at=datetime(2026, 10, 1, 14),
        end_at=datetime(2026, 10, 1, 18),
        location="Paris",
        attendee_count=50,
    )
    session.add(event)
    session.commit()
    session.expire_all()

    saved_event = session.scalars(select(Event)).one()
    assert saved_event.contract.client.sales_contact.role.name == "commercial"
    assert saved_event.support_contact.role.name == "support"
    assert saved_event.contract.amount_due == Decimal("25.00")


def test_unknown_commercial_is_rejected(session):
    client = Client(
        full_name="Client test",
        email="client@example.test",
        phone="123456789",
        company_name="Entreprise test",
        sales_contact_id=999,
    )
    session.add(client)

    with pytest.raises(IntegrityError):
        session.commit()


@pytest.mark.parametrize("amount_due", [Decimal("-1.00"), Decimal("101.00")])
def test_invalid_contract_balance_is_rejected(session, amount_due):
    client = create_client(session)
    contract = Contract(
        client=client,
        total_amount=Decimal("100.00"),
        amount_due=amount_due,
    )
    session.add(contract)

    with pytest.raises(IntegrityError):
        session.commit()


def test_event_end_must_follow_start(session):
    client = create_client(session)
    contract = Contract(
        client=client,
        total_amount=Decimal("100.00"),
        amount_due=Decimal("100.00"),
    )
    event = Event(
        contract=contract,
        name="Événement test",
        start_at=datetime(2026, 10, 1, 18),
        end_at=datetime(2026, 10, 1, 14),
        location="Paris",
        attendee_count=50,
    )
    session.add(event)

    with pytest.raises(IntegrityError):
        session.commit()
