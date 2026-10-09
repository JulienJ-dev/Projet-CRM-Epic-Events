"""Vérifie la lecture complète et le refus d'accès avant les requêtes métier."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from authentication import (
    AuthenticationError,
    create_token,
    login,
    save_token,
)
from models import Client, Contract, Event, Role
from read_data import get_all_clients, get_all_contracts, get_all_events


READERS = [
    (get_all_clients, "clients"),
    (get_all_contracts, "contracts"),
    (get_all_events, "events"),
]


@pytest.fixture
def business_data(session, client, users):
    other_client = Client(
        full_name="Autre client",
        email="other@example.test",
        phone="0123456789",
        company_name="Autre entreprise",
        sales_contact=users["other_commercial"],
    )
    signed_contract = Contract(
        client=client, total_amount=100, amount_due=0, is_signed=True
    )
    unsigned_contract = Contract(
        client=client, total_amount=200, amount_due=200, is_signed=False
    )
    other_contract = Contract(
        client=other_client, total_amount=300, amount_due=150, is_signed=True
    )
    assigned_event = Event(
        contract=signed_contract,
        support_contact=users["support"],
        name="Événement affecté",
        start_at=datetime(2026, 11, 1, 14),
        end_at=datetime(2026, 11, 1, 18),
        location="Paris",
        attendee_count=10,
    )
    unassigned_event = Event(
        contract=other_contract,
        name="Événement sans support",
        start_at=datetime(2026, 11, 2, 14),
        end_at=datetime(2026, 11, 2, 18),
        location="Lyon",
        attendee_count=20,
    )
    session.add_all([unsigned_contract, assigned_event, unassigned_event])
    session.commit()
    return {
        "clients": sorted([client.id, other_client.id]),
        "contracts": sorted(
            [signed_contract.id, unsigned_contract.id, other_contract.id]
        ),
        "events": sorted([assigned_event.id, unassigned_event.id]),
    }


@pytest.fixture
def business_queries(session):
    queries = []

    def record_query(execution):
        if execution.is_select:
            for description in execution.statement.column_descriptions:
                if description["entity"] in (Client, Contract, Event):
                    queries.append(execution.statement)

    event.listen(session, "do_orm_execute", record_query)
    yield queries
    event.remove(session, "do_orm_execute", record_query)


@pytest.mark.parametrize("department", ["gestion", "commercial", "support"])
@pytest.mark.parametrize("read_function, table", READERS)
def test_each_department_reads_all_records(
    session, business_data, users, auth_config, department, read_function, table
):
    save_token(create_token(users[department]))
    support_id = users["support"].id
    session.expunge_all()

    records = read_function(session)

    assert [record.id for record in records] == business_data[table]
    if table == "clients":
        assert {record.sales_contact.full_name for record in records} == {
            "commercial",
            "other_commercial",
        }
    elif table == "contracts":
        assert {record.is_signed for record in records} == {True, False}
        assert {record.amount_due for record in records} == {0, 150, 200}
        assert {record.client.sales_contact.full_name for record in records} == {
            "commercial",
            "other_commercial",
        }
    else:
        assert {record.name for record in records} == {
            "Événement affecté",
            "Événement sans support",
        }
        assert {record.support_contact_id for record in records} == {
            None,
            support_id,
        }


@pytest.mark.parametrize("read_function, table", READERS)
def test_empty_tables_return_an_empty_list(
    session, manager, auth_config, read_function, table
):
    login(session, manager.email, "Mot de passe de test 2026")

    assert read_function(session) == []


@pytest.mark.parametrize("state", ["missing", "expired", "invalid", "deleted"])
@pytest.mark.parametrize("read_function, table", READERS)
def test_invalid_sessions_are_rejected_before_reading_business_data(
    session,
    business_data,
    users,
    auth_config,
    business_queries,
    monkeypatch,
    state,
    read_function,
    table,
):
    if state == "expired":
        monkeypatch.setattr("authentication.TOKEN_LIFETIME", timedelta(hours=-1))
        save_token(create_token(users["gestion"]))
    elif state == "invalid":
        save_token("jeton invalide")
    elif state == "deleted":
        save_token(create_token(users["gestion"]))
        session.delete(users["gestion"])
        session.commit()

    business_queries.clear()
    with pytest.raises(AuthenticationError):
        read_function(session)

    assert business_queries == []


@pytest.mark.parametrize("read_function, table", READERS)
def test_current_role_is_checked_before_reading_business_data(
    session,
    test_engine,
    business_data,
    users,
    auth_config,
    business_queries,
    read_function,
    table,
):
    user = users["gestion"]
    save_token(create_token(user))
    with Session(test_engine) as other_session, other_session.begin():
        current = other_session.get(type(user), user.id)
        current.role = Role(name="inconnu")

    with pytest.raises(PermissionError):
        read_function(session)

    assert business_queries == []


@pytest.mark.parametrize("read_function, table", READERS)
def test_main_relations_are_loaded_with_the_results(
    session, test_engine, business_data, users, auth_config, read_function, table
):
    save_token(create_token(users["gestion"]))
    with Session(test_engine) as other_session:
        records = read_function(other_session)

    # Ces relations restent accessibles après la fermeture de la session.
    if table == "clients":
        assert all(record.sales_contact.full_name for record in records)
    elif table == "contracts":
        assert all(record.client.sales_contact.full_name for record in records)
    else:
        assert all(record.contract.client.sales_contact.full_name for record in records)
        assert {
            record.support_contact.full_name if record.support_contact else None
            for record in records
        } == {"support", None}
