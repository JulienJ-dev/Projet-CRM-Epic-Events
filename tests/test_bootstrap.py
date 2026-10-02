"""Vérifie l'outil de création du premier compte sans saisir de vrais secrets."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import create_first_manager as bootstrap
from models import Collaborator
from security import verify_password


def test_bootstrap_creates_a_manager(test_engine, monkeypatch, capsys):
    monkeypatch.setattr(bootstrap, "engine", test_engine)
    answers = iter(["Dawn", "dawn@example.test"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    password = "Mot de passe de test 2026"
    monkeypatch.setattr(bootstrap, "getpass", lambda prompt: password)
    bootstrap.main()
    with Session(test_engine) as session:
        user = session.scalars(select(Collaborator)).one()
        assert user.role.name == "gestion"
        assert verify_password(user.password_hash, password)
    output = capsys.readouterr().out
    assert "Numéro d'employé" in output
    assert password not in output


def test_mismatched_passwords_create_no_account(test_engine, monkeypatch):
    monkeypatch.setattr(bootstrap, "engine", test_engine)
    answers = iter(["Dawn", "dawn@example.test"])
    passwords = iter(["Mot de passe de test 2026", "autre mot de passe"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    monkeypatch.setattr(bootstrap, "getpass", lambda prompt: next(passwords))
    with pytest.raises(ValueError):
        bootstrap.main()
    with Session(test_engine) as session:
        assert session.scalar(select(func.count()).select_from(Collaborator)) == 0


def test_bootstrap_refuses_an_existing_account(
    test_engine, session, users, monkeypatch
):
    session.commit()
    monkeypatch.setattr(bootstrap, "engine", test_engine)
    with pytest.raises(PermissionError):
        bootstrap.main()
