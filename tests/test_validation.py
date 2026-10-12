"""Vérifie les types, les limites et les valeurs normalisées avant écriture."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from validation import (
    validate_amount,
    validate_count,
    validate_date,
    validate_datetime,
    validate_email,
    validate_fields,
    validate_id,
    validate_notes,
    validate_text,
)


def test_normalized_values():
    assert validate_text(" Dawn ", "Nom", 100) == "Dawn"
    assert validate_email(" DAWN@example.test ") == "dawn@example.test"
    assert validate_id(1) == 1
    assert validate_date(date(2026, 1, 1)) == date(2026, 1, 1)
    assert validate_datetime(datetime(2026, 1, 1)) == datetime(2026, 1, 1)
    assert validate_count(0) == 0
    assert validate_notes(None) is None
    assert validate_notes(" Notes ") == "Notes"


@pytest.mark.parametrize("value", [" ", "a" * 101, None, 42])
def test_invalid_text(value):
    with pytest.raises(ValueError):
        validate_text(value, "Nom", 100)


@pytest.mark.parametrize("value", ["invalide", "a@b", "a b@example.test", None])
def test_invalid_email(value):
    with pytest.raises(ValueError):
        validate_email(value)


@pytest.mark.parametrize("value", [0, -1, True, "1", 1.5, 2**63])
def test_invalid_id(value):
    with pytest.raises(ValueError):
        validate_id(value)


@pytest.mark.parametrize("value", ["2026-01-01", None, datetime(2026, 1, 1)])
def test_invalid_date(value):
    with pytest.raises(ValueError):
        validate_date(value)


@pytest.mark.parametrize("value", [None, date(2026, 1, 1), datetime.now(timezone.utc)])
def test_invalid_datetime(value):
    with pytest.raises(ValueError):
        validate_datetime(value)


@pytest.mark.parametrize("value", [0, 12.5, "12.50", Decimal("12.50"), "9999999999.99"])
def test_valid_amount(value):
    assert validate_amount(value) == Decimal(str(value))


@pytest.mark.parametrize(
    "value", [-1, "10000000000", "1.001", "NaN", "Infinity", "invalide", True, None]
)
def test_invalid_amount(value):
    with pytest.raises(ValueError):
        validate_amount(value)


@pytest.mark.parametrize("value", [-1, 1.5, True, "10", 2**31])
def test_invalid_attendee_count(value):
    with pytest.raises(ValueError):
        validate_count(value)


def test_invalid_notes_and_update_fields():
    with pytest.raises(ValueError):
        validate_notes(42)
    with pytest.raises(ValueError):
        validate_fields({}, {"name"})
    with pytest.raises(ValueError, match="id"):
        validate_fields({"id": 2}, {"name"})
    validate_fields({"name": "test"}, {"name"})
