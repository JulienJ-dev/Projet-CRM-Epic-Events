"""Vérifie les conversions et les arguments refusés par le terminal."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from cli_parser import build_parser


def test_update_argument_types():
    args = build_parser().parse_args(
        [
            "contracts",
            "update",
            "1",
            "--client-id",
            "2",
            "--total",
            "100.50",
            "--due",
            "0",
            "--created-at",
            "2026-01-01",
            "--unsigned",
        ]
    )
    assert args.record_id == 1
    assert args.client_id == 2
    assert args.total_amount == Decimal("100.50")
    assert args.amount_due == Decimal("0")
    assert args.created_at == date(2026, 1, 1)
    assert args.is_signed is False
    event = build_parser().parse_args(
        [
            "events",
            "update",
            "1",
            "--start",
            "2026-11-01 14:00",
            "--attendees",
            "0",
        ]
    )
    assert event.start_at == datetime(2026, 11, 1, 14)
    assert event.attendee_count == 0
    assert build_parser().parse_args(["contracts", "update", "1"]).is_signed is None


@pytest.mark.parametrize(
    "arguments",
    [
        ["clients", "show", "0"],
        ["clients", "show", "abc"],
        ["clients", "show", str(2**63)],
        ["clients", "create"],
        ["clients", "update", "1", "--created-at", "2026-02-30"],
        ["clients", "update", "1", "--created-at", "20260101"],
        ["contracts", "update", "1", "--total", "NaN"],
        ["contracts", "update", "1", "--total", "1.001"],
        ["contracts", "update", "1", "--total", "abc"],
        ["contracts", "update", "1", "--signed", "--unsigned"],
        ["events", "update", "1", "--attendees", "-1"],
        ["events", "update", "1", "--attendees", "abc"],
        ["events", "update", "1", "--start", "2026-11-01T14:00"],
        ["events", "update", "1", "--start", "2026-02-30 14:00"],
        ["events", "update", "1", "--start", "2026-1-1 14:00"],
        ["events", "update", "1", "--notes", "test", "--clear-notes"],
        ["events", "list", "--mine", "--unassigned"],
        ["events", "assign", "1"],
        ["events", "assign", "1", "--support-id", "0"],
        ["collaborators", "update", "1", "--department", "admin"],
        ["collaborators", "create", "--password", "secret"],
    ],
)
def test_invalid_arguments_are_rejected(arguments):
    with pytest.raises(SystemExit) as error:
        build_parser().parse_args(arguments)
    assert error.value.code == 2


@pytest.mark.parametrize(
    "arguments",
    [
        ["--help"],
        ["clients", "--help"],
        ["contracts", "update", "--help"],
        ["events", "assign", "--help"],
        ["collaborators", "delete", "--help"],
    ],
)
def test_help_is_available_without_authentication(arguments, capsys):
    with pytest.raises(SystemExit) as error:
        build_parser().parse_args(arguments)
    assert error.value.code == 0
    assert "usage:" in capsys.readouterr().out
