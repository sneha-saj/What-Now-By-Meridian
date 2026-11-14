"""Turn missing fields into short, tap-to-answer questions (max 3)."""

from datetime import date, timedelta

from models import Facts, Option, Question
from rules import missing_fields

MAX_QUESTIONS = 3


def _question(field: str, today: date) -> Question:
    if field == "citizenship":
        return Question(field=field, question="Which passport do you hold?", options=[
            Option(label="Outside the EU", value="non_eu"),
            Option(label="EU / EEA country", value="eu"),
            Option(label="Finnish", value="finnish"),
        ])
    if field == "permit_type":
        return Question(field=field, question="What kind of residence permit do you have?", options=[
            Option(label="Work-based", value="work"),
            Option(label="Specialist", value="specialist"),
            Option(label="EU Blue Card", value="eu_blue_card"),
            Option(label="Student", value="student"),
            Option(label="Family", value="family"),
            Option(label="Permanent", value="permanent"),
            Option(label="Not sure", value="other"),
        ])
    if field == "job_end_date":
        return Question(field=field, kind="date", question="When was (or is) your last day of work?", options=[
            Option(label="Today", value=today.isoformat()),
            Option(label="About a week ago", value=(today - timedelta(days=7)).isoformat()),
            Option(label="About a month ago", value=(today - timedelta(days=30)).isoformat()),
        ])
    if field == "over_two_years_on_work_permit":
        return Question(field=field, question="Have you had a work-based permit for more than 2 years in total?", options=[
            Option(label="Yes, more than 2 years", value=True),
            Option(label="No, less", value=False),
        ])
    raise ValueError(field)


def questions_for(facts: Facts, today: date | None = None) -> list[Question]:
    today = today or date.today()
    return [_question(f, today) for f in missing_fields(facts.to_rules())[:MAX_QUESTIONS]]
