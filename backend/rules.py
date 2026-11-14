"""Deadline calculations driven by the Finland country configuration."""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Optional

from countries.finland import DEADLINE_RULES, PERMIT_TYPES, SOURCE_TITLE, SOURCE_URL

MIGRI_SOURCE = {"title": SOURCE_TITLE, "url": SOURCE_URL}
Citizenship = Literal["finnish", "eu", "non_eu"]
PermitType = Literal[
    "work_based", "specialist_blue_card", "student", "family_based", "permanent",
    "eu_eea_citizen", "not_sure",
    # Compatibility values accepted by the existing intake model and saved demos.
    "work", "work-based", "specialist", "eu_blue_card", "specialist-eu-blue-card",
    "family", "eu-eea-citizen", "not-sure", "other",
]
Status = Literal["ok", "not_applicable", "needs_info", "unsupported"]

_PERMIT_IDS = {entry["id"] for entry in PERMIT_TYPES}
_PERMIT_ALIASES = {
    "work": "work_based",
    "work-based": "work_based",
    "specialist": "specialist_blue_card",
    "eu_blue_card": "specialist_blue_card",
    "specialist-eu-blue-card": "specialist_blue_card",
    "family": "family_based",
    "eu-eea-citizen": "eu_eea_citizen",
    "not-sure": "not_sure",
    "other": "not_sure",
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
    rule_id: Optional[str] = None


def add_months(day: date, months: int) -> date:
    """Add calendar months, clamping to the last valid day of the target month."""
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _canonical_permit(permit_type: str) -> str:
    permit = _PERMIT_ALIASES.get(permit_type, permit_type)
    if permit not in _PERMIT_IDS:
        raise ValueError(f"Unsupported permit_type: {permit_type}")
    return permit


def _condition_matches(condition: dict, permit_type: str, years: float | None) -> bool:
    if condition["permit_type"] != permit_type:
        return False
    duration = condition.get("years_on_work_permit")
    if duration is None:
        return True
    if years is None:
        return False
    value = duration["value"]
    if duration["operator"] == "lte":
        return years <= value
    if duration["operator"] == "gt":
        return years > value
    raise ValueError(f"Unsupported duration operator: {duration['operator']}")


def _rules_for(permit_type: str, years: float | None) -> list[dict]:
    return [
        rule
        for rule in DEADLINE_RULES
        if any(_condition_matches(condition, permit_type, years) for condition in rule["applies_when"])
    ]


def _possible_dates(job_end_date: date | None) -> list[dict]:
    possibilities = []
    seen_months = set()
    for rule in DEADLINE_RULES:
        months = rule["months"]
        if months is None or months in seen_months:
            continue
        seen_months.add(months)
        possibilities.append({
            "months": months,
            "deadline_date": add_months(job_end_date, months) if job_end_date else None,
            "rule_id": rule["id"],
        })
    return sorted(possibilities, key=lambda item: item["months"])


def calculate_deadline(
    permit_type: str,
    years_on_work_permit: float | None,
    job_end_date: date | None,
) -> dict:
    """Return deadline details from the configured Finland rules.

    An uncertain permit type (or missing work-permit duration) returns both
    configured deadline possibilities rather than choosing one.
    """
    permit = _canonical_permit(permit_type)
    source_url = DEADLINE_RULES[0]["source_url"]

    if permit == "not_sure" or (permit == "work_based" and years_on_work_permit is None):
        return {
            "applies": True,
            "months": None,
            "deadline_date": None,
            "rule_id": None,
            "source_url": source_url,
            "explanation": "Your permit type or time on a work-based permit is unclear. The possible protection periods are shown so you can confirm which applies with Migri.",
            "possible_dates": _possible_dates(job_end_date),
        }

    matches = _rules_for(permit, years_on_work_permit)
    if not matches:
        raise ValueError(f"No configured deadline rule applies to permit_type: {permit}")
    rule = matches[0]
    months = rule["months"]
    applies = months is not None
    deadline_date = add_months(job_end_date, months) if applies and job_end_date else None
    explanation = rule["description"]
    if applies and deadline_date:
        explanation = f"{explanation} Based on your last day of work, the date is {deadline_date.isoformat()}."
    return {
        "applies": applies,
        "months": months,
        "deadline_date": deadline_date,
        "rule_id": rule["id"],
        "source_url": rule["source_url"],
        "explanation": explanation,
    }


def _canonical_or_citizen(permit_type: str | None, citizenship: str | None) -> str | None:
    if citizenship in ("finnish", "eu"):
        return "eu_eea_citizen"
    if permit_type is None:
        return None
    return _canonical_permit(permit_type)


def missing_fields(f: DeadlineInput) -> list[str]:
    if f.citizenship is None:
        return ["citizenship", "permit_type", "job_end_date"]
    permit = _canonical_or_citizen(f.permit_type, f.citizenship)
    if permit == "eu_eea_citizen" or permit in {"student", "family_based", "permanent", "not_sure"}:
        return []
    missing = []
    if permit is None:
        missing.append("permit_type")
    if f.job_end_date is None:
        missing.append("job_end_date")
    if permit == "work_based" and f.over_two_years_on_work_permit is None:
        missing.append("over_two_years_on_work_permit")
    return missing


def permit_months(f: DeadlineInput) -> Optional[int]:
    permit = _canonical_or_citizen(f.permit_type, f.citizenship)
    if permit is None or permit in {"student", "family_based", "permanent", "eu_eea_citizen", "not_sure"}:
        return None
    years = None
    if permit == "work_based" and f.over_two_years_on_work_permit is not None:
        years = 3 if f.over_two_years_on_work_permit else 1
    rule = next(iter(_rules_for(permit, years)), None)
    return rule["months"] if rule else None


def compute_deadline(f: DeadlineInput, today: Optional[date] = None) -> DeadlineResult:
    """Compatibility adapter for existing API callers."""
    today = today or date.today()
    if f.citizenship is None:
        missing = missing_fields(f)
        return DeadlineResult(status="needs_info", reason="A couple more answers and we can work out your date.", missing=missing)
    permit = _canonical_or_citizen(f.permit_type, f.citizenship)
    if permit is None:
        return DeadlineResult(status="needs_info", reason="A couple more answers and we can work out your date.", missing=missing_fields(f))
    years = None
    if permit == "work_based" and f.over_two_years_on_work_permit is not None:
        years = 3 if f.over_two_years_on_work_permit else 1
    if permit == "work_based" and years is None:
        return DeadlineResult(status="needs_info", reason="A couple more answers and we can work out your date.", missing=missing_fields(f))
    result = calculate_deadline(permit, years, f.job_end_date)
    if not result["applies"]:
        return DeadlineResult(status="not_applicable", reason=result["explanation"], rule_id=result["rule_id"])
    if permit == "not_sure":
        return DeadlineResult(status="unsupported", reason=result["explanation"])
    if result["deadline_date"] is None:
        return DeadlineResult(status="needs_info", reason="A couple more answers and we can work out your date.", missing=["job_end_date"], rule_id=result["rule_id"])
    return DeadlineResult(
        status="ok",
        reason=result["explanation"],
        deadline=result["deadline_date"],
        months=result["months"],
        days_left=(result["deadline_date"] - today).days,
        rule_id=result["rule_id"],
        source={"title": SOURCE_TITLE, "url": result["source_url"]},
    )
