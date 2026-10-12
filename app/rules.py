from datetime import datetime


def reaction_minutes(created_at: datetime, first_staff_reply: datetime | None):
    if first_staff_reply is None:
        return None
    return max(0.0, (first_staff_reply - created_at).total_seconds() / 60)


def sla_breached(created_at, first_staff_reply, sla_minutes, now):
    endpoint = first_staff_reply if first_staff_reply is not None else now
    return (endpoint - created_at).total_seconds() > sla_minutes * 60


def can_transition(old, new):
    return (old, new) in {('new', 'in_progress'), ('in_progress', 'closed')}
