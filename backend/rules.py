"""Plain-code deadline engine backed exclusively by the Finland country config."""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Optional

from countries.finland import DEADLINE_RULES, SOURCE_TITLE, SOURCE_URL

MIGRI_SOURCE = {"title": SOURCE_TITLE, "url": SOURCE_URL}
Citizenship = Literal["finnish", "eu", "non_eu"]
PermitType = Literal["work", "work-based", "specialist", "eu_blue_card", "specialist-eu-blue-card", "student", "family", "family-based", "permanent", "eu-eea-citizen", "not-sure", "other"]
Status = Literal["ok", "not_applicable", "needs_info", "unsupported"]
SIX_MONTH_PERMITS = {"specialist", "eu_blue_card", "specialist-eu-blue-card"}
NOT_TIED_TO_JOB = {"permanent", "student", "family", "family-based", "eu-eea-citizen"}
_THREE_MONTH_RULE = next(r for r in DEADLINE_RULES if r["months"] == 3)
_SIX_MONTH_RULE = next(r for r in DEADLINE_RULES if r["months"] == 6)
_NOT_APPLICABLE_RULE = next(r for r in DEADLINE_RULES if r["months"] is None)

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
    rule_id: Optional[str] = None

def add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year, month = d.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))

def missing_fields(f: DeadlineInput) -> list[str]:
    if f.citizenship is None:
        return ["citizenship", "permit_type", "job_end_date"]
    if f.citizenship in ("finnish", "eu") or f.permit_type in NOT_TIED_TO_JOB or f.permit_type in ("other", "not-sure"):
        return []
    missing = []
    if f.permit_type is None:
        missing.append("permit_type")
    if f.job_end_date is None:
        missing.append("job_end_date")
    if f.permit_type in (None, "work", "work-based") and f.over_two_years_on_work_permit is None:
        missing.append("over_two_years_on_work_permit")
    return missing

def permit_months(f: DeadlineInput) -> Optional[int]:
    if f.permit_type in SIX_MONTH_PERMITS:
        return _SIX_MONTH_RULE["months"]
    if f.permit_type in ("work", "work-based"):
        if f.over_two_years_on_work_permit is None:
            return None
        return _SIX_MONTH_RULE["months"] if f.over_two_years_on_work_permit else _THREE_MONTH_RULE["months"]
    return None

def compute_deadline(f: DeadlineInput, today: Optional[date] = None) -> DeadlineResult:
    today = today or date.today()
    if f.citizenship in ("finnish", "eu") or f.permit_type == "eu-eea-citizen":
        return DeadlineResult(status="not_applicable", reason="As an EU/EEA or Finnish citizen you don't need a residence permit, so there's no deadline to stay.", rule_id=_NOT_APPLICABLE_RULE["id"])
    if f.permit_type in NOT_TIED_TO_JOB:
        labels = {"permanent": "Permanent residence", "student": "A student permit", "family": "A family-based permit", "family-based": "A family-based permit"}
        return DeadlineResult(status="not_applicable", reason=f"{labels[f.permit_type]} isn't tied to your job, so losing your job doesn't start a deadline.", rule_id=_NOT_APPLICABLE_RULE["id"])
    if f.permit_type in ("other", "not-sure"):
        return DeadlineResult(status="unsupported", reason="We can't calculate this for your permit type yet. Migri can tell you exactly.")
    missing = missing_fields(f)
    if missing:
        return DeadlineResult(status="needs_info", reason="A couple more answers and we can work out your date.", missing=missing)
    months = permit_months(f)
    assert months is not None and f.job_end_date is not None
    deadline = add_months(f.job_end_date, months)
    rule = _SIX_MONTH_RULE if months == 6 else _THREE_MONTH_RULE
    why = "you hold a specialist permit or EU Blue Card" if f.permit_type in SIX_MONTH_PERMITS else ("you've had a work-based permit for more than 2 years" if months == 6 else "you're on a work-based permit")
    return DeadlineResult(status="ok", reason=f"You have {months} months from your last day of work, because {why}.", deadline=deadline, months=months, days_left=(deadline-today).days, rule_id=rule["id"])
