from datetime import datetime, timedelta, timezone
import pytest
from app.rules import can_transition, reaction_minutes, sla_breached

START = datetime(2026, 9, 1, tzinfo=timezone.utc)


def test_reaction_is_time_to_first_reply():
    assert reaction_minutes(START, START + timedelta(minutes=35)) == 35


def test_no_reply_has_no_reaction_time():
    assert reaction_minutes(START, None) is None


def test_sla_exact_boundary_is_allowed():
    assert not sla_breached(START, START + timedelta(minutes=60), 60, START + timedelta(days=1))


def test_reply_after_limit_is_breach():
    assert sla_breached(START, START + timedelta(minutes=61), 60, START + timedelta(days=1))


def test_unanswered_ticket_becomes_overdue():
    assert sla_breached(START, None, 60, START + timedelta(minutes=61))
    assert not sla_breached(START, None, 60, START + timedelta(minutes=59))


def test_answer_on_time_stops_sla_clock():
    assert not sla_breached(START, START + timedelta(minutes=10), 60, START + timedelta(days=10))


@pytest.mark.parametrize('old,new,allowed', [('new', 'in_progress', True), ('in_progress', 'closed', True), ('new', 'closed', False), ('closed', 'new', False), ('new', 'new', False)])
def test_status_transitions(old, new, allowed):
    assert can_transition(old, new) == allowed
