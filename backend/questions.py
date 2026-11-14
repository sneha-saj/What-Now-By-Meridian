"""Which facts the deadline still needs, as short tap-to-answer questions (max 3).

Only asks what the deadline calculation needs. Never asks for permit numbers or passport details.
"""

from __future__ import annotations

from datetime import date, timedelta

from countries.finland import QUESTION_BANK, REQUIRED_FIELDS
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
    """Required fields the deadline still needs, in the config's fixed order."""
    permit = canonical_permit(f)
    needed = []
    for field in REQUIRED_FIELDS:
        if field == "citizenship_group" and f.citizenship_group is None:
            needed.append(field)
        elif field == "permit_type" and permit is None:
            needed.append(field)
        elif field == "years_on_work_permit" and permit == "work_based" and f.years_on_work_permit is None:
            needed.append(field)
        elif field == "job_end_date" and permit not in NO_DEADLINE_PERMITS and f.job_end_date is None:
            needed.append(field)
    if permit in NO_DEADLINE_PERMITS:  # nothing else matters for the deadline
        needed = [x for x in needed if x == "citizenship_group"] if permit != "eu_eea_citizen" else []
    return needed[:MAX_QUESTIONS]


def next_field(f: Facts) -> str | None:
    """Ask about job loss, then only the facts needed for the deadline."""
    if f.lost_job is None and f.job_end_date is None:
        return "lost_job"
    needed = needed_fields(f)
    return needed[0] if needed else None


def question(field: str, today: date | None = None) -> Question:
    today = today or date.today()
    q = QUESTION_BANK[field]
    if q["options"] == "relative_dates":
        options = [
            Option(value=today.isoformat(), label="Today"),
            Option(value=APPROX + (today - timedelta(days=7)).isoformat(), label="About a week ago"),
            Option(value=APPROX + (today - timedelta(days=30)).isoformat(), label="About a month ago"),
        ]
    else:
        options = [Option(**o) for o in q["options"]]
    return Question(id=field, question=q["question"], kind=q.get("kind", "choice"), options=options)


def questions_for(f: Facts, today: date | None = None) -> list[Question]:
    """Up to 3 questions for the required fields still missing (used by /intake)."""
    return [question(field, today) for field in needed_fields(f)]
