"""Vérifie les écritures, les validations et les limites des permissions."""

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from authentication import (
    AuthenticationError,
    create_token,
    get_current_user,
    save_token,
)
from models import Client, Collaborator, Contract, Event, Role
from security import verify_password
from write_data import (
    assign_support,
    create_client,
    create_collaborator,
    create_contract,
    create_event,
    update_client,
    update_collaborator,
    update_contract,
    update_event,
)


PASSWORD = "Mot de passe de test 2026"
START = datetime(2026, 11, 1, 14)
END = datetime(2026, 11, 1, 18)


@pytest.fixture
def connected(session, users, auth_config):
    session.commit()

    def connect(department):
        save_token(create_token(users[department]))

    connect("gestion")
    return connect


@pytest.fixture
def records(session, users, connected):
    connected("commercial")
    first_client = create_client(
        session, "Client", "client@example.test", "0123456789", "Entreprise"
    )
    second_client = create_client(
        session, "Second", "second@example.test", "+33123456789", "Entreprise 2"
    )
    connected("other_commercial")
    other_client = create_client(session, "Autre", "other@example.test", "123", "Autre")
    connected("gestion")
    first_contract = create_contract(
        session, first_client.id, "100", "50", is_signed=True
    )
    second_contract = create_contract(
        session, second_client.id, "200", "0", is_signed=True
    )
    other_contract = create_contract(
        session, other_client.id, "300", "300", is_signed=True
    )
    unsigned = create_contract(session, first_client.id, "100", "100")
    connected("commercial")
    first_event = create_event(
        session, first_contract.id, "Événement", START, END, "Paris", 10
    )
    connected("gestion")
    assign_support(session, first_event.id, users["support"].id)
    session.commit()
    return {
        "client": first_client.id,
        "second_client": second_client.id,
        "other_client": other_client.id,
        "contract": first_contract.id,
        "second_contract": second_contract.id,
        "other_contract": other_contract.id,
        "unsigned": unsigned.id,
        "event": first_event.id,
    }


def test_management_creates_and_updates_a_collaborator(session, connected):
    user = create_collaborator(
        session, " Bill ", " BILL@example.test ", PASSWORD, "commercial"
    )
    employee_id = user.id
    update_collaborator(
        session,
        employee_id,
        full_name="Kate",
        email=" KATE@example.test ",
        password="Nouveau mot de passe 2026",
        role_name="support",
    )
    session.commit()
    session.expunge_all()
    saved = session.get(Collaborator, employee_id)
    assert saved.full_name == "Kate"
    assert saved.email == "kate@example.test"
    assert saved.role.name == "support"
    assert verify_password(saved.password_hash, "Nouveau mot de passe 2026")
    assert not verify_password(saved.password_hash, PASSWORD)


def test_client_creation_and_update(session, connected, users):
    connected("commercial")
    client = create_client(
        session, " Client ", " CLIENT@example.test ", "+331234", " Société "
    )
    assert client.sales_contact_id == users["commercial"].id
    update_client(
        session,
        client.id,
        full_name="Nouveau nom",
        email=" NEW@example.test ",
        phone="0123",
        company_name="Autre entreprise",
        created_at=date(2025, 1, 1),
        updated_at=date(2026, 1, 1),
    )
    session.commit()
    session.refresh(client)
    assert client.full_name == "Nouveau nom"
    assert client.email == "new@example.test"
    assert client.phone == "0123"
    assert client.company_name == "Autre entreprise"
    assert client.created_at == date(2025, 1, 1)
    assert client.updated_at == date(2026, 1, 1)


def test_management_updates_all_contract_fields(session, records, connected):
    contract = update_contract(
        session,
        records["unsigned"],
        client_id=records["other_client"],
        total_amount="500.25",
        amount_due="10.50",
        is_signed=True,
        created_at=date(2025, 1, 1),
    )
    session.commit()
    session.refresh(contract)
    assert contract.client_id == records["other_client"]
    assert contract.total_amount == Decimal("500.25")
    assert contract.amount_due == Decimal("10.50")
    assert contract.is_signed is True
    assert contract.created_at == date(2025, 1, 1)


def test_commercial_updates_a_contract_between_own_clients(session, records, connected):
    connected("commercial")
    contract = update_contract(
        session,
        records["unsigned"],
        client_id=records["second_client"],
        amount_due=0,
        is_signed=True,
    )
    session.commit()
    session.refresh(contract)
    assert contract.client_id == records["second_client"]
    assert contract.is_signed
    assert contract.amount_due == 0


def test_support_updates_all_event_information(session, records, connected):
    connected("support")
    current = update_event(
        session,
        records["event"],
        contract_id=records["second_contract"],
        name="Nouveau nom",
        start_at=datetime(2026, 12, 1, 10),
        end_at=datetime(2026, 12, 1, 12),
        location="Lyon",
        attendee_count=20,
        notes=" Nouvelles notes ",
    )
    session.commit()
    session.refresh(current)
    assert current.contract_id == records["second_contract"]
    assert current.name == "Nouveau nom"
    assert current.start_at == datetime(2026, 12, 1, 10)
    assert current.end_at == datetime(2026, 12, 1, 12)
    assert current.location == "Lyon"
    assert current.attendee_count == 20
    assert current.notes == "Nouvelles notes"
    update_event(session, current.id, notes=None)
    assert current.notes is None


def test_management_reassigns_and_removes_support(session, records, connected, users):
    other_support = create_collaborator(
        session, "Autre support", "support2@example.test", PASSWORD, "support"
    )
    current = assign_support(session, records["event"], other_support.id)
    assert current.support_contact_id == other_support.id
    assert current.support_contact is other_support
    assign_support(session, current.id, None)
    session.commit()
    session.refresh(current)
    assert current.support_contact_id is None
    assert current.support_contact is None


@pytest.mark.parametrize("department", ["commercial", "support"])
def test_non_management_cannot_manage_accounts(session, connected, users, department):
    connected(department)
    with pytest.raises(PermissionError):
        create_collaborator(session, "Compte", "new@example.test", PASSWORD, "gestion")
    with pytest.raises(PermissionError):
        update_collaborator(session, users[department].id, role_name="gestion")


@pytest.mark.parametrize("department", ["gestion", "support"])
def test_only_commercial_creates_clients(session, connected, department):
    connected(department)
    with pytest.raises(PermissionError):
        create_client(session, "Client", "client@example.test", "123", "Entreprise")


@pytest.mark.parametrize("department", ["commercial", "support"])
def test_only_management_creates_contracts(session, records, connected, department):
    connected(department)
    with pytest.raises(PermissionError):
        create_contract(session, records["client"], 100, 100)


@pytest.mark.parametrize("department", ["gestion", "support", "other_commercial"])
def test_event_creation_is_limited_to_the_clients_commercial(
    session, records, connected, department
):
    connected(department)
    with pytest.raises(PermissionError):
        create_event(session, records["contract"], "Événement", START, END, "Paris", 10)


def test_event_creation_requires_a_signed_contract(session, records, connected):
    connected("commercial")
    with pytest.raises(PermissionError):
        create_event(session, records["unsigned"], "Événement", START, END, "Paris", 10)


def test_commercial_cannot_modify_or_take_other_clients_contracts(
    session, records, connected
):
    connected("commercial")
    with pytest.raises(PermissionError):
        update_client(session, records["other_client"], full_name="Vol")
    with pytest.raises(PermissionError):
        update_contract(session, records["other_contract"], client_id=records["client"])
    with pytest.raises(PermissionError):
        update_contract(session, records["contract"], client_id=records["other_client"])
    with pytest.raises(PermissionError):
        update_client(session, records["client"], sales_contact_id=999)


@pytest.mark.parametrize("department", ["gestion", "commercial", "other_commercial"])
def test_only_assigned_support_updates_event_information(
    session, records, connected, department
):
    connected(department)
    with pytest.raises(PermissionError):
        update_event(session, records["event"], notes="Interdit")


def test_support_cannot_reassign_or_claim_an_event(session, records, connected, users):
    connected("support")
    with pytest.raises(PermissionError):
        update_event(
            session, records["event"], support_contact_id=None, notes="Interdit"
        )
    with pytest.raises(PermissionError):
        assign_support(session, records["event"], users["support"].id)
    connected("gestion")
    assign_support(session, records["event"], None)
    connected("support")
    with pytest.raises(PermissionError):
        update_event(session, records["event"], notes="Interdit")


def test_management_cannot_mix_assignment_and_other_event_fields(
    session, records, connected
):
    with pytest.raises(PermissionError):
        update_event(
            session, records["event"], support_contact_id=None, name="Interdit"
        )


@pytest.mark.parametrize("contact", ["gestion", "commercial", "missing"])
def test_invalid_support_is_rejected(session, records, users, contact):
    contact_id = 999 if contact == "missing" else users[contact].id
    with pytest.raises(ValueError):
        assign_support(session, records["event"], contact_id)


def test_department_changes_preserve_links_and_revoke_old_permissions(
    session, records, users, connected
):
    update_collaborator(session, users["commercial"].id, role_name="support")
    update_collaborator(session, users["support"].id, role_name="commercial")
    session.commit()
    assert (
        session.get(Client, records["client"]).sales_contact_id
        == users["commercial"].id
    )
    assert (
        session.get(Event, records["event"]).support_contact_id == users["support"].id
    )
    connected("commercial")
    with pytest.raises(PermissionError):
        update_client(session, records["client"], full_name="Interdit")
    connected("support")
    with pytest.raises(PermissionError):
        update_event(session, records["event"], notes="Interdit")
    connected("gestion")
    assign_support(session, records["event"], None)


def test_signature_can_change_but_new_event_relationship_requires_a_signed_contract(
    session, records, connected
):
    contract = update_contract(session, records["contract"], is_signed=False)
    assert contract.is_signed is False
    connected("support")
    # Les événements existants restent modifiables après un changement de statut.
    update_event(session, records["event"], notes="Statut à vérifier")
    with pytest.raises(ValueError):
        update_event(session, records["event"], contract_id=records["unsigned"])


@pytest.mark.parametrize(
    "changes",
    [
        {"full_name": "Valide", "email": "invalide"},
        {"password": "court"},
        {"email": "commercial@example.test"},
        {"role_name": "inconnu"},
        {"id": 99},
        {"password_hash": "forgé"},
        {},
    ],
)
def test_invalid_account_updates_do_not_modify_the_object(
    session, connected, users, changes
):
    original = users["support"]
    before = (
        original.full_name,
        original.email,
        original.password_hash,
        original.role_id,
    )
    with pytest.raises(ValueError):
        update_collaborator(session, original.id, **changes)
    assert (
        original.full_name,
        original.email,
        original.password_hash,
        original.role_id,
    ) == before
    assert original not in session.dirty


@pytest.mark.parametrize(
    "changes",
    [
        {"full_name": "Valide", "phone": ""},
        {"email": None},
        {"company_name": "a" * 151},
        {"created_at": "hier"},
        {"created_at": date(2027, 1, 1), "updated_at": date(2026, 1, 1)},
        {"id": 99},
        {},
    ],
)
def test_invalid_client_updates_do_not_modify_the_object(
    session, records, connected, changes
):
    connected("commercial")
    original = session.get(Client, records["client"])
    before = (original.full_name, original.email, original.phone, original.created_at)
    with pytest.raises(ValueError):
        update_client(session, original.id, **changes)
    assert (
        original.full_name,
        original.email,
        original.phone,
        original.created_at,
    ) == before
    assert original not in session.dirty


@pytest.mark.parametrize(
    "changes",
    [
        {"total_amount": 20},
        {"amount_due": -1},
        {"total_amount": "1.001"},
        {"is_signed": "oui"},
        {"created_at": datetime(2026, 1, 1)},
        {"client_id": 999},
        {"client_id": True},
        {"id": 99},
        {},
    ],
)
def test_invalid_contract_updates_do_not_modify_the_object(session, records, changes):
    original = session.get(Contract, records["contract"])
    before = (original.total_amount, original.amount_due, original.client_id)
    with pytest.raises(ValueError):
        update_contract(session, original.id, **changes)
    assert (original.total_amount, original.amount_due, original.client_id) == before
    assert original not in session.dirty


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "Valide", "end_at": START},
        {"start_at": "demain"},
        {"name": ""},
        {"location": "a" * 256},
        {"attendee_count": -1},
        {"notes": 123},
        {"contract_id": 999},
        {"id": 99},
        {},
    ],
)
def test_invalid_event_updates_do_not_modify_the_object(
    session, records, connected, changes
):
    connected("support")
    original = session.get(Event, records["event"])
    before = (original.name, original.start_at, original.end_at, original.contract_id)
    with pytest.raises(ValueError):
        update_event(session, original.id, **changes)
    assert (
        original.name,
        original.start_at,
        original.end_at,
        original.contract_id,
    ) == before
    assert original not in session.dirty


@pytest.mark.parametrize(
    "model, operation",
    [
        (
            Collaborator,
            lambda session: create_collaborator(
                session, "Test", "bad", PASSWORD, "support"
            ),
        ),
        (
            Client,
            lambda session: create_client(
                session, "Test", "test@example.test", "", "Entreprise"
            ),
        ),
        (Contract, lambda session: create_contract(session, 999, 100, 100)),
        (
            Event,
            lambda session: create_event(session, 999, "Test", START, END, "Paris", 10),
        ),
    ],
)
def test_invalid_creations_add_no_object(session, connected, model, operation):
    connected("commercial" if model in (Client, Event) else "gestion")
    before = list(session.scalars(select(model)))
    with pytest.raises(ValueError):
        operation(session)
    assert list(session.scalars(select(model))) == before
    assert not session.new


def test_department_and_password_changes_affect_the_current_session(
    session, connected, users
):
    manager_id = users["gestion"].id
    update_collaborator(session, manager_id, role_name="support")
    session.commit()
    with pytest.raises(PermissionError):
        create_collaborator(
            session, "Test", "test@example.test", PASSWORD, "commercial"
        )
    assert get_current_user(session).role.name == "support"
    # Une autre gestion peut ensuite changer son mot de passe.
    role = session.scalar(select(Role).where(Role.name == "gestion"))
    other = Collaborator(
        full_name="Gestion 2",
        email="gestion2@example.test",
        password_hash="test",
        role=role,
    )
    session.add(other)
    session.commit()
    old_token = create_token(users["gestion"])
    save_token(create_token(other))
    update_collaborator(session, manager_id, password=PASSWORD)
    session.commit()
    save_token(old_token)
    with pytest.raises(AuthenticationError):
        get_current_user(session)


def test_ownership_is_reloaded_before_contract_writes(
    session, test_engine, records, connected, users
):
    connected("commercial")
    cached = session.get(Contract, records["contract"])
    assert cached.client.sales_contact_id == users["commercial"].id
    with Session(test_engine) as other_session, other_session.begin():
        current = other_session.get(Client, records["client"])
        current.sales_contact_id = users["other_commercial"].id
    with pytest.raises(PermissionError):
        update_contract(session, cached.id, client_id=records["second_client"])
    with pytest.raises(PermissionError):
        create_event(session, cached.id, "Interdit", START, END, "Paris", 10)


OPERATIONS = [
    lambda session: create_collaborator(
        session, "Test", "test@example.test", PASSWORD, "support"
    ),
    lambda session: update_collaborator(session, 999, full_name="Test"),
    lambda session: create_client(
        session, "Test", "test@example.test", "123", "Entreprise"
    ),
    lambda session: update_client(session, 999, full_name="Test"),
    lambda session: create_contract(session, 999, 100, 100),
    lambda session: update_contract(session, 999, amount_due=0),
    lambda session: create_event(session, 999, "Test", START, END, "Paris", 10),
    lambda session: update_event(session, 999, notes="Test"),
    lambda session: assign_support(session, 999, None),
]


@pytest.mark.parametrize(
    "department, operation",
    [
        (
            "gestion",
            lambda session: update_collaborator(session, 999, full_name="Test"),
        ),
        ("commercial", lambda session: update_client(session, 999, full_name="Test")),
        ("gestion", lambda session: update_contract(session, 999, amount_due=0)),
        ("support", lambda session: update_event(session, 999, notes="Test")),
    ],
)
def test_missing_update_target_is_rejected(session, connected, department, operation):
    connected(department)
    with pytest.raises(ValueError, match="introuvable"):
        operation(session)


def test_caller_transaction_rolls_back_on_error(test_engine, connected):
    with Session(test_engine) as session:
        with pytest.raises(ValueError):
            with session.begin():
                user = create_collaborator(
                    session, "Test", "rollback@example.test", PASSWORD, "support"
                )
                update_collaborator(session, user.id, email="invalide")
        assert (
            session.scalar(
                select(Collaborator).where(
                    Collaborator.email == "rollback@example.test"
                )
            )
            is None
        )


def test_permission_failure_does_not_flush_pending_changes(
    session, records, connected, test_engine
):
    connected("support")
    client = session.get(Client, records["client"])
    client.full_name = "Modification en attente"
    writes = []

    def record_write(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            writes.append(statement)

    event.listen(test_engine, "before_cursor_execute", record_write)
    try:
        with pytest.raises(PermissionError):
            create_collaborator(
                session, "Test", "test@example.test", PASSWORD, "gestion"
            )
        assert writes == []
    finally:
        event.remove(test_engine, "before_cursor_execute", record_write)
        session.rollback()


@pytest.mark.parametrize("operation", OPERATIONS)
def test_missing_session_prevents_all_writes(
    session, auth_config, test_engine, operation
):
    writes = []

    def record_write(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            writes.append(statement)

    event.listen(test_engine, "before_cursor_execute", record_write)
    try:
        with pytest.raises(AuthenticationError):
            operation(session)
        assert writes == []
    finally:
        event.remove(test_engine, "before_cursor_execute", record_write)
