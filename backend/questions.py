"""Which facts the deadline still needs, as short tap-to-answer questions (max 3).

Only asks what the deadline calculation needs. Never asks for permit numbers or passport details.
"""

from __future__ import annotations

from datetime import date, timedelta

from countries.finland import PERMIT_TYPES
from models import Facts, Option, Question
from rules import _canonical_permit

MAX_QUESTIONS = 3
APPROX = "about:"  # prefix on quick-reply dates that are only approximate
NO_DEADLINE_PERMITS = {"student", "family_based", "permanent", "eu_eea_citizen"}


def canonical_permit(f: Facts) -> str | None:
    """Permit id the rules engine understands, or None if we don't know it yet."""
    if f.citizenship_group == "eu_eea":
        return "eu_eea_citizen"
    if f.permit_type is None:
        return None
    try:
        return _canonical_permit(f.permit_type)
    except ValueError:
        return "not_sure"


def needed_fields(f: Facts) -> list[str]:
    needed = []
    if f.citizenship_group is None:
        needed.append("citizenship_group")
    permit = canonical_permit(f)
    if permit in NO_DEADLINE_PERMITS:
        return needed
    if permit is None:
        needed.append("permit_type")
    if permit == "work_based" and f.years_on_work_permit is None:
        needed.append("years_on_work_permit")
    if f.job_end_date is None:
        needed.append("job_end_date")
    return needed[:MAX_QUESTIONS]


def _question(field: str, today: date) -> Question:
    if field == "citizenship_group":
        return Question(id=field, question="Are you a citizen of an EU or EEA country?", options=[
            Option(value="eu_eea", label="Yes, EU / EEA"),
            Option(value="other", label="No, another country"),
            Option(value="unknown", label="Not sure"),
        ])
    if field == "permit_type":
        return Question(id=field, question="What kind of residence permit do you have?", options=[
            Option(value=p["id"], label=p["label"]) for p in PERMIT_TYPES if p["id"] != "eu_eea_citizen"
        ])
    if field == "years_on_work_permit":
        return Question(id=field, question="How long have you had a work-based permit in Finland, in total?", options=[
            Option(value="under_2", label="2 years or less"),
            Option(value="over_2", label="More than 2 years"),
            Option(value="not_sure", label="Not sure"),
        ])
    if field == "job_end_date":
        return Question(id=field, kind="date", question="When was (or is) your last day of work?", options=[
            Option(value=today.isoformat(), label="Today"),
            Option(value=APPROX + (today - timedelta(days=7)).isoformat(), label="About a week ago"),
            Option(value=APPROX + (today - timedelta(days=30)).isoformat(), label="About a month ago"),
        ])
    raise ValueError(field)


def questions_for(f: Facts, today: date | None = None) -> list[Question]:
    today = today or date.today()
    return [_question(field, today) for field in needed_fields(f)]
