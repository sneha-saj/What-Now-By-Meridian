from datetime import date

import pytest

from rules import DeadlineInput, add_months, compute_deadline, missing_fields
from countries.finland import DEADLINE_RULES, TRUSTED_DOMAINS

TODAY = date(2026, 11, 14)
END = date(2026, 11, 1)


def work(**kw):
    base = dict(citizenship="non_eu", permit_type="work", job_end_date=END,
                over_two_years_on_work_permit=False)
    base.update(kw)
    return DeadlineInput(**base)


def test_work_permit_three_months():
    r = compute_deadline(work(), today=TODAY)
    assert r.status == "ok"
    assert r.months == 3
    assert r.deadline == date(2027, 2, 1)
    assert r.days_left == (date(2027, 2, 1) - TODAY).days
    assert r.rule_id == "work-based-three-months"


def test_work_permit_over_two_years_six_months():
    r = compute_deadline(work(over_two_years_on_work_permit=True), today=TODAY)
    assert r.months == 6
    assert r.deadline == date(2027, 5, 1)
    assert r.rule_id == "specialist-or-long-term-work-six-months"


@pytest.mark.parametrize("permit", ["specialist", "eu_blue_card"])
def test_specialist_and_blue_card_six_months(permit):
    # Duration on permit is irrelevant for these.
    r = compute_deadline(work(permit_type=permit, over_two_years_on_work_permit=None), today=TODAY)
    assert r.status == "ok"
    assert r.months == 6


@pytest.mark.parametrize("permit", ["permanent", "student", "family"])
def test_permits_not_tied_to_job(permit):
    r = compute_deadline(work(permit_type=permit), today=TODAY)
    assert r.status == "not_applicable"
    assert r.deadline is None
    assert r.rule_id == "not-tied-to-employment"


@pytest.mark.parametrize("citizenship", ["eu", "finnish"])
def test_eu_and_finnish_citizens_not_applicable(citizenship):
    r = compute_deadline(DeadlineInput(citizenship=citizenship), today=TODAY)
    assert r.status == "not_applicable"


def test_other_permit_unsupported():
    assert compute_deadline(work(permit_type="other"), today=TODAY).status == "unsupported"


def test_needs_info_lists_missing_fields():
    r = compute_deadline(DeadlineInput(citizenship="non_eu", permit_type="work"), today=TODAY)
    assert r.status == "needs_info"
    assert r.missing == ["job_end_date", "over_two_years_on_work_permit"]


def test_missing_fields_nothing_known():
    assert missing_fields(DeadlineInput()) == ["citizenship", "permit_type", "job_end_date"]


def test_missing_fields_blue_card_does_not_ask_duration():
    f = DeadlineInput(citizenship="non_eu", permit_type="eu_blue_card")
    assert missing_fields(f) == ["job_end_date"]


def test_past_deadline_has_negative_days_left():
    r = compute_deadline(work(job_end_date=date(2026, 1, 1)), today=TODAY)
    assert r.days_left < 0


@pytest.mark.parametrize("start,months,expected", [
    (date(2026, 11, 30), 3, date(2027, 2, 28)),   # clamp to Feb end
    (date(2027, 11, 30), 3, date(2028, 2, 29)),   # leap year
    (date(2026, 8, 31), 6, date(2027, 2, 28)),
    (date(2026, 1, 15), 12, date(2027, 1, 15)),
])
def test_add_months_clamps(start, months, expected):
    assert add_months(start, months) == expected


def test_finland_country_config_contains_sources_and_all_rule_metadata():
    assert TRUSTED_DOMAINS == ["migri.fi", "kela.fi", "infofinland.fi", "tyomarkkinatori.fi"]
    assert {rule["months"] for rule in DEADLINE_RULES} == {None, 3, 6}
    for rule in DEADLINE_RULES:
        assert {"id", "description", "months", "applies_to", "source_url", "in_force_since", "last_verified"} <= rule.keys()
        assert rule["source_url"].startswith("https://migri.fi/")
        assert rule["in_force_since"] == "2025-06-11"
