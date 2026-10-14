"""Vérifie les commandes métier avec une base et un jeton de test."""

from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

import epicevents
from authentication import create_token, save_token
from models import Client, Collaborator, Contract, Event
from security import verify_password


PASSWORD = "Mot de passe de test 2026"


@pytest.fixture
def cli_data(session, test_engine, users, auth_config, monkeypatch):
    monkeypatch.setattr(epicevents, "engine", test_engine)
    monkeypatch.setenv("COLUMNS", "160")
    client = Client(
        full_name="Kevin",
        email="kevin@example.test",
        phone="0123456789",
        company_name="Entreprise",
        sales_contact=users["commercial"],
    )
    other_client = Client(
        full_name="Lou",
        email="lou@example.test",
        phone="0123456789",
        company_name="Autre entreprise",
        sales_contact=users["other_commercial"],
    )
    paid = Contract(client=client, total_amount=100, amount_due=0, is_signed=True)
    unsigned = Contract(client=client, total_amount=200, amount_due=200)
    unpaid = Contract(
        client=other_client, total_amount=300, amount_due=150, is_signed=True
    )
    assigned = Event(
        contract=paid,
        name="Affecté",
        support_contact=users["support"],
        start_at=datetime(2026, 11, 1, 14),
        end_at=datetime(2026, 11, 1, 18),
        location="Paris",
        attendee_count=10,
        notes="Notes initiales",
    )
    unassigned = Event(
        contract=unpaid,
        name="Sans support",
        start_at=datetime(2026, 11, 2, 14),
        end_at=datetime(2026, 11, 2, 18),
        location="Lyon",
        attendee_count=20,
    )
    session.add_all([unsigned, assigned, unassigned])
    session.commit()
    ids = {
        "client": client.id,
        "other_client": other_client.id,
        "paid": paid.id,
        "unsigned": unsigned.id,
        "unpaid": unpaid.id,
        "assigned": assigned.id,
        "unassigned": unassigned.id,
        "commercial": users["commercial"].id,
        "support": users["support"].id,
    }

    def connect(department):
        save_token(create_token(users[department]))

    connect("gestion")
    return ids, connect


@pytest.mark.parametrize(
    "entity, expected",
    [
        ("clients", "Kevin"),
        ("contracts", "200.00"),
        ("events", "Sans support"),
        ("collaborators", "other_commercial"),
    ],
)
def test_lists(entity, expected, cli_data, capsys):
    assert epicevents.main([entity, "list"]) == 0
    output = capsys.readouterr().out
    assert expected in output
    assert "hash de test" not in output


@pytest.mark.parametrize(
    "entity, key, expected",
    [
        ("clients", "client", "kevin@example.test"),
        ("contracts", "paid", "kevin@example.test"),
        ("events", "assigned", "Notes initiales"),
        ("collaborators", "support", "support@example.test"),
    ],
)
def test_details(entity, key, expected, cli_data, capsys):
    ids, connect = cli_data
    assert epicevents.main([entity, "show", str(ids[key])]) == 0
    assert expected in capsys.readouterr().out


def test_contract_and_event_filters(cli_data, capsys):
    ids, connect = cli_data
    assert epicevents.main(["contracts", "list", "--unsigned", "--unpaid"]) == 0
    output = capsys.readouterr().out
    assert "200.00" in output
    assert "100.00" not in output
    assert "300.00" not in output
    assert epicevents.main(["events", "list", "--unassigned"]) == 0
    output = capsys.readouterr().out
    assert "Sans support" in output
    assert "Affecté" not in output
    connect("support")
    assert epicevents.main(["events", "list", "--mine"]) == 0
    output = capsys.readouterr().out
    assert "Affecté" in output
    assert "Sans support" not in output


def test_collaborator_creation_and_update(cli_data, test_engine, monkeypatch, capsys):
    monkeypatch.setattr(epicevents, "getpass", lambda prompt: PASSWORD)
    assert (
        epicevents.main(
            [
                "collaborators",
                "create",
                "--name",
                "Nouveau",
                "--email",
                "new@example.test",
                "--department",
                "commercial",
            ]
        )
        == 0
    )
    with Session(test_engine) as session:
        user = session.scalar(
            select(Collaborator).where(Collaborator.email == "new@example.test")
        )
        user_id = user.id
        assert verify_password(user.password_hash, PASSWORD)
    assert (
        epicevents.main(
            [
                "collaborators",
                "update",
                str(user_id),
                "--department",
                "support",
                "--name",
                "Autre nom",
                "--email",
                "other@example.test",
                "--change-password",
            ]
        )
        == 0
    )
    with Session(test_engine) as session:
        user = session.get(Collaborator, user_id)
        assert user.role.name == "support"
        assert user.full_name == "Autre nom"
        assert user.email == "other@example.test"
    assert PASSWORD not in capsys.readouterr().out


def test_password_confirmation_prevents_creation(
    cli_data, monkeypatch, test_engine, capsys
):
    passwords = iter([PASSWORD, "autre mot de passe"])
    monkeypatch.setattr(epicevents, "getpass", lambda prompt: next(passwords))
    assert (
        epicevents.main(
            [
                "collaborators",
                "create",
                "--name",
                "Test",
                "--email",
                "failed@example.test",
                "--department",
                "support",
            ]
        )
        == 1
    )
    assert "correspondent" in capsys.readouterr().err
    with Session(test_engine) as session:
        assert (
            session.scalar(
                select(Collaborator).where(Collaborator.email == "failed@example.test")
            )
            is None
        )


def test_client_commands(cli_data, test_engine):
    ids, connect = cli_data
    connect("commercial")
    assert (
        epicevents.main(
            [
                "clients",
                "create",
                "--name",
                "Nouveau client",
                "--email",
                "newclient@example.test",
                "--phone",
                "0123",
                "--company",
                "Startup",
            ]
        )
        == 0
    )
    with Session(test_engine) as session:
        client = session.scalar(
            select(Client).where(Client.email == "newclient@example.test")
        )
        client_id = client.id
        assert client.sales_contact_id == ids["commercial"]
    assert (
        epicevents.main(
            [
                "clients",
                "update",
                str(client_id),
                "--name",
                "Modifié",
                "--email",
                "updated@example.test",
                "--phone",
                "0456",
                "--company",
                "Autre",
                "--created-at",
                "2025-01-01",
                "--updated-at",
                "2026-01-01",
            ]
        )
        == 0
    )
    with Session(test_engine) as session:
        assert session.get(Client, client_id).email == "updated@example.test"


def test_contract_commands(cli_data, test_engine):
    ids, connect = cli_data
    assert (
        epicevents.main(
            [
                "contracts",
                "create",
                "--client-id",
                str(ids["client"]),
                "--total",
                "400",
                "--due",
                "400",
                "--signed",
            ]
        )
        == 0
    )
    with Session(test_engine) as session:
        contract_id = session.scalar(
            select(Contract.id).where(Contract.total_amount == 400)
        )
    assert (
        epicevents.main(
            [
                "contracts",
                "update",
                str(contract_id),
                "--client-id",
                str(ids["other_client"]),
                "--total",
                "500",
                "--due",
                "0",
                "--unsigned",
                "--created-at",
                "2025-01-01",
            ]
        )
        == 0
    )
    with Session(test_engine) as session:
        contract = session.get(Contract, contract_id)
        assert contract.client_id == ids["other_client"]
        assert contract.total_amount == 500
        assert contract.amount_due == 0
        assert contract.is_signed is False


def test_event_creation_assignment_and_update(cli_data, test_engine):
    ids, connect = cli_data
    connect("commercial")
    assert (
        epicevents.main(
            [
                "events",
                "create",
                "--contract-id",
                str(ids["paid"]),
                "--name",
                "Nouvel événement",
                "--start",
                "2026-12-01 10:00",
                "--end",
                "2026-12-01 12:00",
                "--location",
                "Paris",
                "--attendees",
                "50",
                "--notes",
                "Test",
            ]
        )
        == 0
    )
    with Session(test_engine) as session:
        event_id = session.scalar(
            select(Event.id).where(Event.name == "Nouvel événement")
        )
    connect("gestion")
    assert (
        epicevents.main(
            ["events", "assign", str(event_id), "--support-id", str(ids["support"])]
        )
        == 0
    )
    connect("support")
    assert (
        epicevents.main(
            [
                "events",
                "update",
                str(event_id),
                "--contract-id",
                str(ids["unpaid"]),
                "--name",
                "Modifié",
                "--start",
                "2026-12-02 10:00",
                "--end",
                "2026-12-02 12:00",
                "--location",
                "Lyon",
                "--attendees",
                "0",
                "--clear-notes",
            ]
        )
        == 0
    )
    with Session(test_engine) as session:
        current = session.get(Event, event_id)
        assert current.contract_id == ids["unpaid"]
        assert current.notes is None
        assert current.attendee_count == 0
        assert current.location == "Lyon"
    connect("gestion")
    assert epicevents.main(["events", "assign", str(event_id), "--clear"]) == 0
    with Session(test_engine) as session:
        assert session.get(Event, event_id).support_contact_id is None


@pytest.mark.parametrize(
    "department, arguments",
    [
        ("support", ["collaborators", "list"]),
        ("commercial", ["collaborators", "show", "1"]),
        ("support", ["collaborators", "update", "1", "--department", "gestion"]),
        ("support", ["collaborators", "delete", "1"]),
        (
            "gestion",
            [
                "clients",
                "create",
                "--name",
                "Test",
                "--email",
                "test@example.test",
                "--phone",
                "123",
                "--company",
                "Test",
            ],
        ),
        (
            "commercial",
            [
                "contracts",
                "create",
                "--client-id",
                "1",
                "--total",
                "100",
                "--due",
                "100",
            ],
        ),
        ("gestion", ["events", "list", "--mine"]),
    ],
)
def test_forbidden_commands(department, arguments, cli_data, capsys, monkeypatch):
    ids, connect = cli_data
    connect(department)
    monkeypatch.setattr(
        "builtins.input", lambda prompt: pytest.fail("Saisie interdite")
    )
    monkeypatch.setattr(
        epicevents, "getpass", lambda prompt: pytest.fail("Saisie interdite")
    )
    assert epicevents.main(arguments) == 1
    assert capsys.readouterr().err


@pytest.mark.parametrize("entity", ["clients", "contracts", "events", "collaborators"])
def test_no_session_rejects_lists(
    entity, test_engine, auth_config, monkeypatch, capsys
):
    monkeypatch.setattr(epicevents, "engine", test_engine)
    assert epicevents.main([entity, "list"]) == 1
    output = capsys.readouterr()
    assert "Connectez-vous" in output.err
    assert "ID" not in output.out


def test_invalid_event_update_is_rolled_back(cli_data, test_engine, capsys):
    ids, connect = cli_data
    connect("support")
    assert (
        epicevents.main(
            [
                "events",
                "update",
                str(ids["assigned"]),
                "--name",
                "À annuler",
                "--end",
                "2026-11-01 13:00",
            ]
        )
        == 1
    )
    output = capsys.readouterr()
    assert "doit suivre" in output.err
    assert "modifié" not in output.out
    with Session(test_engine) as session:
        assert session.get(Event, ids["assigned"]).name == "Affecté"


def test_no_fields_and_unknown_id(cli_data, capsys):
    assert epicevents.main(["contracts", "update", "999", "--due", "0"]) == 1
    assert "introuvable" in capsys.readouterr().err
    ids, connect = cli_data
    assert epicevents.main(["contracts", "update", str(ids["paid"])]) == 1
    assert "au moins un champ" in capsys.readouterr().err


def test_delete_cancellation_and_confirmation(
    cli_data, test_engine, monkeypatch, capsys
):
    ids, connect = cli_data
    monkeypatch.setattr("builtins.input", lambda prompt: "NON")
    assert epicevents.main(["collaborators", "delete", str(ids["support"])]) == 0
    assert "annulée" in capsys.readouterr().out
    with Session(test_engine) as session:
        assert session.get(Collaborator, ids["support"]) is not None
    monkeypatch.setattr("builtins.input", lambda prompt: "OUI")
    assert epicevents.main(["collaborators", "delete", str(ids["support"])]) == 0
    with Session(test_engine) as session:
        assert session.get(Collaborator, ids["support"]) is None
        assert session.get(Event, ids["assigned"]).support_contact_id is None


def test_delete_requires_and_uses_a_replacement_commercial(
    cli_data, test_engine, monkeypatch, capsys
):
    ids, connect = cli_data
    monkeypatch.setattr("builtins.input", lambda prompt: "OUI")
    assert epicevents.main(["collaborators", "delete", str(ids["commercial"])]) == 1
    assert "remplacement" in capsys.readouterr().err
    with Session(test_engine) as session:
        other_id = session.scalar(
            select(Collaborator.id).where(
                Collaborator.email == "other_commercial@example.test"
            )
        )
    assert (
        epicevents.main(
            [
                "collaborators",
                "delete",
                str(ids["commercial"]),
                "--replacement-commercial",
                str(other_id),
            ]
        )
        == 0
    )
    with Session(test_engine) as session:
        assert session.get(Collaborator, ids["commercial"]) is None
        assert session.get(Client, ids["client"]).sales_contact_id == other_id
        assert session.get(Contract, ids["paid"]) is not None


def test_markup_is_displayed_literally(cli_data, test_engine, capsys):
    with Session(test_engine) as session, session.begin():
        user = session.scalar(
            select(Collaborator).where(Collaborator.email == "gestion@example.test")
        )
        user.full_name = "[bold]Dawn[/bold]"
    assert epicevents.main(["whoami"]) == 0
    assert "[bold]Dawn[/bold]" in capsys.readouterr().out


def test_database_error_is_generic(cli_data, monkeypatch, capsys):
    from sqlalchemy.exc import OperationalError

    def fail(*args, **kwargs):
        raise OperationalError("requête", {}, Exception("secret-local"))

    monkeypatch.setattr("cli_commands.read_data.get_all_clients", fail)
    assert epicevents.main(["clients", "list"]) == 1
    output = capsys.readouterr().err
    assert "Erreur de base" in output
    assert "secret-local" not in output


@pytest.mark.parametrize("entity", ["clients", "contracts", "events"])
def test_empty_business_lists(
    entity, test_engine, manager, auth_config, monkeypatch, capsys
):
    monkeypatch.setattr(epicevents, "engine", test_engine)
    save_token(create_token(manager))
    assert epicevents.main([entity, "list"]) == 0
    assert "Aucun résultat" in capsys.readouterr().out


@pytest.mark.parametrize("entity", ["clients", "contracts", "events", "collaborators"])
def test_missing_detail(entity, cli_data, capsys):
    assert epicevents.main([entity, "show", "999"]) == 1
    assert "introuvable" in capsys.readouterr().err


@pytest.mark.parametrize("entity", ["clients", "contracts", "events", "collaborators"])
def test_details_require_a_session(
    entity, test_engine, auth_config, monkeypatch, capsys
):
    monkeypatch.setattr(epicevents, "engine", test_engine)
    assert epicevents.main([entity, "show", "1"]) == 1
    assert "Connectez-vous" in capsys.readouterr().err


@pytest.mark.parametrize("replacement", ["self", "support", "missing"])
def test_invalid_replacement_preserves_the_account_and_clients(
    replacement, cli_data, test_engine
):
    from write_data import delete_collaborator

    ids, connect = cli_data
    replacement_id = {
        "self": ids["commercial"],
        "support": ids["support"],
        "missing": 999,
    }[replacement]
    with Session(test_engine) as session:
        with pytest.raises(ValueError):
            delete_collaborator(session, ids["commercial"], replacement_id)
        assert session.get(Collaborator, ids["commercial"]) is not None
        assert session.get(Client, ids["client"]).sales_contact_id == ids["commercial"]
        assert not session.dirty


def test_direct_services_validate_filter_arguments(cli_data, test_engine):
    from read_data import get_all_contracts, get_all_events

    with Session(test_engine) as session:
        with pytest.raises(ValueError):
            get_all_contracts(session, unpaid="oui")
        with pytest.raises(ValueError):
            get_all_events(session, mine="oui")
        with pytest.raises(ValueError):
            get_all_events(session, mine=True, unassigned=True)


def test_terminal_control_characters_are_not_printed(cli_data, test_engine, capsys):
    ids, connect = cli_data
    with Session(test_engine) as session, session.begin():
        client = session.get(Client, ids["client"])
        client.full_name = "[bold]Kevin[/bold]\x1b[2J"
    assert epicevents.main(["clients", "show", str(ids["client"])]) == 0
    output = capsys.readouterr().out
    assert "[bold]Kevin[/bold]" in output
    assert "\x1b" not in output
