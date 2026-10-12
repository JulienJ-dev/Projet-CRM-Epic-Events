"""Validations communes avant l'écriture des données dans la base."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def validate_text(value, label, max_length):
    if not isinstance(value, str):
        raise ValueError(f"{label} doit être un texte.")
    value = value.strip()
    if not value or len(value) > max_length:
        raise ValueError(f"{label} doit contenir entre 1 et {max_length} caractères.")
    return value


def validate_email(value):
    value = validate_text(value, "L'adresse email", 255).lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        raise ValueError("L'adresse email est invalide.")
    return value


def validate_id(value):
    if type(value) is not int or not 0 < value <= 9223372036854775807:
        raise ValueError("L'identifiant doit être un entier positif.")
    return value


def validate_date(value):
    if type(value) is not date:
        raise ValueError("La date doit être un objet date.")
    return value


def validate_datetime(value):
    if not isinstance(value, datetime) or value.tzinfo is not None:
        raise ValueError("La date et l'heure doivent être un datetime sans fuseau.")
    return value


def validate_amount(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("Le montant doit être un nombre décimal.")
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Le montant doit être un nombre décimal.") from None
    if not amount.is_finite() or not 0 <= amount <= Decimal("9999999999.99"):
        raise ValueError("Le montant doit être compris entre 0 et 9999999999.99.")
    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Le montant ne peut pas avoir plus de deux décimales.")
    return amount.quantize(Decimal("0.01"))


def validate_count(value):
    if type(value) is not int or not 0 <= value <= 2147483647:
        raise ValueError(
            "Le nombre de participants doit être un entier entre 0 et 2147483647."
        )
    return value


def validate_notes(value):
    if value is not None and not isinstance(value, str):
        raise ValueError("Les notes doivent être un texte ou None.")
    return value.strip() if value is not None else None


def validate_fields(changes, allowed_fields):
    if not changes:
        raise ValueError("Indiquez au moins un champ à modifier.")
    unknown = set(changes) - set(allowed_fields)
    if unknown:
        raise ValueError("Champs non modifiables : " + ", ".join(sorted(unknown)))
