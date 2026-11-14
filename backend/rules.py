"""Deadline engine for "how long can I stay after losing my job?".

Plain code, no AI. Every number here must be explainable to a judge (and a
worried user) by pointing at a rule, not a model output.

Rules (Finnish Aliens Act job-seeking period, simplified for the hackathon):
- Work-based residence permit: 3 months from the day employment ended.
- 6 months if the person holds a specialist permit / EU Blue Card, or has
  held a work-based permit for more than 2 years.
- Not applicable: permanent residents, students, family-based permits,
  EU/EEA and Finnish citizens (their right to stay isn't tied to the job).

This is not legal advice; the UI always links to Migri for confirmation.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Optional

MIGRI_SOURCE = {
    "title": "Migri – Residence permits and losing your job",
    # TODO: verify the exact page URL before the demo.
    "url": "https://migri.fi/en/home",
}

Citizenship = Literal["finnish", "eu", "non_eu"]
PermitType = Literal[
    "work", "specialist", "eu_blue_card", "student", "family", "permanent", "other"
]
Status = Literal["ok", "not_applicable", "needs_info", "unsupported"]

SIX_MONTH_PERMITS = {"specialist", "eu_blue_card"}
NOT_TIED_TO_JOB = {
    "permanent": "Permanent residence isn't tied to a job, so losing your job doesn't start a deadline.",
    "student": "A student permit isn't tied to your job, so there's no job-seeking deadline from this.",
    "family": "A family-based permit isn't tied to your job, so there's no job-seeking deadline from this.",
}


@dataclass
class DeadlineInput:
    citizenship: Optional[Citizenship] = None
    permit_type: Optional[PermitType] = None
    job_end_date: Optional[date] = None
    over_two_years_on_work_permit: Optional[bool] = None


@dataclass
class DeadlineResult:
    status: Status
    reason: str
    deadline: Optional[date] = None
    months: Optional[int] = None
    days_left: Optional[int] = None
    missing: list[str] = field(default_factory=list)
    source: dict = field(default_factory=lambda: dict(MIGRI_SOURCE))


def add_months(d: date, months: int) -> date:
    """Add calendar months, clamping to the last day of the target month."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def missing_fields(f: DeadlineInput) -> list[str]:
    """Fields still needed to compute a deadline, in the order we'd ask them."""
    if f.citizenship is None:
        return ["citizenship", "permit_type", "job_end_date"]
    if f.citizenship in ("finnish", "eu"):
        return []
    missing: list[str] = []
    if f.permit_type is None:
        missing.append("permit_type")
    elif f.permit_type in NOT_TIED_TO_JOB or f.permit_type == "other":
        return []
    if f.job_end_date is None:
        missing.append("job_end_date")
    if f.permit_type in (None, "work") and f.over_two_years_on_work_permit is None:
        missing.append("over_two_years_on_work_permit")
    return missing


def permit_months(f: DeadlineInput) -> Optional[int]:
    if f.permit_type in SIX_MONTH_PERMITS:
        return 6
    if f.permit_type == "work":
        if f.over_two_years_on_work_permit is None:
            return None
        return 6 if f.over_two_years_on_work_permit else 3
    return None


def compute_deadline(f: DeadlineInput, today: Optional[date] = None) -> DeadlineResult:
    today = today or date.today()

    if f.citizenship in ("finnish", "eu"):
        return DeadlineResult(
            status="not_applicable",
            reason="As an EU/EEA or Finnish citizen you don't need a residence permit, so there's no deadline to stay.",
        )
    if f.permit_type in NOT_TIED_TO_JOB:
        return DeadlineResult(status="not_applicable", reason=NOT_TIED_TO_JOB[f.permit_type])
    if f.permit_type == "other":
        return DeadlineResult(
            status="unsupported",
            reason="We can't calculate this for your permit type yet. Migri can tell you exactly.",
        )

    missing = missing_fields(f)
    if missing:
        return DeadlineResult(
            status="needs_info",
            reason="A couple more answers and we can work out your date.",
            missing=missing,
        )

    months = permit_months(f)
    assert months is not None and f.job_end_date is not None  # guaranteed by missing_fields
    deadline = add_months(f.job_end_date, months)

    if f.permit_type in SIX_MONTH_PERMITS:
        why = "you hold a specialist permit or EU Blue Card"
    elif months == 6:
        why = "you've had a work-based permit for more than 2 years"
    else:
        why = "you're on a work-based permit"

    return DeadlineResult(
        status="ok",
        reason=f"You have {months} months from your last day of work, because {why}.",
        deadline=deadline,
        months=months,
        days_left=(deadline - today).days,
    )
