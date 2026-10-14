"""Vérifie un parcours complet avec plusieurs processus et départements."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

import epicevents
from accounts import create_collaborator, create_first_manager
from authentication import login
from database import create_db_engine
from init_db import initialize_database
from models import Client, Contract, Event


def test_workflow_between_processes(auth_config, tmp_path):
    password = "Mot de passe de test 2026"
    database_url = "sqlite:///" + (tmp_path / "crm.db").as_posix()
    engine = create_db_engine(database_url)
    initialize_database(engine)
    with Session(engine) as session, session.begin():
        manager = create_first_manager(session, "Dawn", "dawn@example.test", password)
        commercial = create_collaborator(
            session, manager, "Bill", "bill@example.test", password, "commercial"
        )
        support = create_collaborator(
            session, manager, "Kate", "kate@example.test", password, "support"
        )
        support_id = support.id
        login(session, commercial.email, password)

    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["COLUMNS"] = "120"

    def command(*arguments):
        result = subprocess.run(
            [sys.executable, str(Path(epicevents.__file__)), *arguments],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout

    def connect(email):
        with Session(engine) as session, session.begin():
            login(session, email, password)

    command(
        "clients",
        "create",
        "--name",
        "Kevin",
        "--email",
        "kevin@example.test",
        "--phone",
        "0123456789",
        "--company",
        "Startup",
    )
    with Session(engine) as session:
        client_id = session.scalars(select(Client.id)).one()
    connect("dawn@example.test")
    command(
        "contracts",
        "create",
        "--client-id",
        str(client_id),
        "--total",
        "100",
        "--due",
        "100",
        "--signed",
    )
    with Session(engine) as session:
        contract_id = session.scalars(select(Contract.id)).one()
    connect("bill@example.test")
    command(
        "events",
        "create",
        "--contract-id",
        str(contract_id),
        "--name",
        "Fête",
        "--start",
        "2026-11-01 14:00",
        "--end",
        "2026-11-01 18:00",
        "--location",
        "Paris",
        "--attendees",
        "10",
    )
    with Session(engine) as session:
        event_id = session.scalars(select(Event.id)).one()
    connect("dawn@example.test")
    command("events", "assign", str(event_id), "--support-id", str(support_id))
    connect("kate@example.test")
    command("events", "update", str(event_id), "--notes", "Organisation confirmée")
    output = command("events", "show", str(event_id))
    assert "Organisation confirmée" in output
    assert "kevin@example.test" in output
    assert "Kate" in output
    assert "Fête" in command("events", "list", "--mine")
    with Session(engine) as session:
        assert session.get(Event, event_id).notes == "Organisation confirmée"
    engine.dispose()
