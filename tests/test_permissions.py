"""Contrôle les droits et leur limitation aux clients ou événements attribués."""

from datetime import datetime

import pytest

from models import Contract, Event, Role
from permissions import has_permission, require_permission


@pytest.fixture
def resources(session, client, users):
    contract = Contract(client=client, total_amount=100, amount_due=100, is_signed=True)
    event = Event(
        contract=contract,
        support_contact=users["support"],
        name="Événement test",
        start_at=datetime(2026, 10, 1, 14),
        end_at=datetime(2026, 10, 1, 18),
        location="Paris",
        attendee_count=10,
    )
    session.add(event)
    session.flush()
    return client, contract, event


@pytest.mark.parametrize("department", ["gestion", "commercial", "support"])
def test_permissions_by_department(users, resources, department):
    client, contract, event = resources
    actions = {
        "read_client": client,
        "read_contract": contract,
        "read_event": event,
        "create_collaborator": None,
        "update_collaborator": None,
        "delete_collaborator": None,
        "create_client": None,
        "update_client": client,
        "create_contract": None,
        "update_contract": contract,
        "create_event": contract,
        "update_event": event,
        "assign_support": event,
    }
    allowed = {
        "gestion": {
            "read_client",
            "read_contract",
            "read_event",
            "create_collaborator",
            "update_collaborator",
            "delete_collaborator",
            "create_contract",
            "update_contract",
            "assign_support",
        },
        "commercial": {
            "read_client",
            "read_contract",
            "read_event",
            "create_client",
            "update_client",
            "update_contract",
            "create_event",
        },
        "support": {"read_client", "read_contract", "read_event", "update_event"},
    }
    for action, resource in actions.items():
        assert has_permission(users[department], action, resource) == (
            action in allowed[department]
        ), action


def test_commercial_cannot_modify_another_commercials_data(users, resources):
    client, contract, event = resources
    other = users["other_commercial"]
    assert not has_permission(other, "update_client", client)
    assert not has_permission(other, "update_contract", contract)
    assert not has_permission(other, "create_event", contract)


def test_event_requires_a_signed_contract(users, resources):
    client, contract, event = resources
    contract.is_signed = False
    assert not has_permission(users["commercial"], "create_event", contract)
    assert has_permission(users["commercial"], "update_contract", contract)


def test_support_cannot_update_unassigned_events(users, resources):
    client, contract, event = resources
    event.support_contact_id = None
    assert not has_permission(users["support"], "update_event", event)


def test_permissions_fail_closed(users, resources):
    client, contract, event = resources
    assert not has_permission(None, "read_client")
    assert not has_permission(users["gestion"], "action_inconnue")
    assert not has_permission(users["commercial"], "update_client")
    assert not has_permission(users["support"], "update_event", client)
    assert not has_permission(users["gestion"], "assign_support")
    users["commercial"].role = Role(name="inconnu")
    assert not has_permission(users["commercial"], "read_client")
    with pytest.raises(PermissionError):
        require_permission(None, "create_collaborator")
