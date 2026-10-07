"""Vérifie les commandes de connexion et la persistance entre deux programmes."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy.orm import Session

import epicevents
from accounts import create_first_manager
from authentication import login
from database import create_db_engine
from init_db import initialize_database


PASSWORD = "Mot de passe de test 2026"


def test_login_whoami_and_logout(
    test_engine, manager, auth_config, monkeypatch, capsys
):
    monkeypatch.setattr(epicevents, "engine", test_engine)
    monkeypatch.setattr("builtins.input", lambda prompt: manager.email)
    monkeypatch.setattr(epicevents, "getpass", lambda prompt: PASSWORD)
    assert epicevents.main(["login"]) == 0
    assert auth_config.exists()
    assert epicevents.main(["whoami"]) == 0
    output = capsys.readouterr().out
    assert "Dawn" in output
    assert "gestion" in output
    assert PASSWORD not in output
    assert auth_config.read_text(encoding="utf-8") not in output
    assert epicevents.main(["logout"]) == 0
    assert epicevents.main(["whoami"]) == 1
    assert "Connectez-vous" in capsys.readouterr().err


def test_wrong_password_returns_an_error(
    test_engine, manager, auth_config, monkeypatch, capsys
):
    monkeypatch.setattr(epicevents, "engine", test_engine)
    monkeypatch.setattr("builtins.input", lambda prompt: manager.email)
    monkeypatch.setattr(epicevents, "getpass", lambda prompt: "mauvais mot de passe")
    assert epicevents.main(["login"]) == 1
    assert "incorrect" in capsys.readouterr().err
    assert not auth_config.exists()


def test_cancelled_login_creates_no_token(test_engine, auth_config, monkeypatch):
    monkeypatch.setattr(epicevents, "engine", test_engine)

    def cancel_input(prompt):
        raise EOFError()

    monkeypatch.setattr("builtins.input", cancel_input)
    assert epicevents.main(["login"]) == 1
    assert not auth_config.exists()


def test_session_is_reused_in_another_process(auth_config, tmp_path):
    database_url = "sqlite:///" + (tmp_path / "test.db").as_posix()
    test_engine = create_db_engine(database_url)
    initialize_database(test_engine)
    with Session(test_engine) as session, session.begin():
        user = create_first_manager(session, "Dawn", "dawn@example.test", PASSWORD)
        login(session, user.email, PASSWORD)
    test_engine.dispose()
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    environment["PYTHONIOENCODING"] = "utf-8"
    script = Path(epicevents.__file__)
    result = subprocess.run(
        [sys.executable, str(script), "whoami"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Dawn" in result.stdout
    assert "gestion" in result.stdout
