from datetime import date

import pytest

from countries.finland import DEADLINE_RULES, PERMIT_TYPES, SOURCE_URL, TRUSTED_DOMAINS
from rules import calculate_deadline


JOB_END = date(2026, 1, 31)


def test_country_config_contains_expected_permits_and_rule_metadata():
    assert TRUSTED_DOMAINS == ["migri.fi", "kela.fi", "infofinland.fi", "tyomarkkinatori.fi"]
    assert {permit["id"] for permit in PERMIT_TYPES} == {
        "work_based", "specialist_blue_card", "student", "family_based",
        "permanent", "eu_eea_citizen", "not_sure",
    }
    assert {rule["months"] for rule in DEADLINE_RULES} == {None, 3, 6}
    for rule in DEADLINE_RULES:
        assert {"id", "description", "months", "applies_to", "source_url", "in_force_since", "last_verified"} <= rule.keys()
        assert rule["source_url"] == SOURCE_URL
        assert rule["in_force_since"] == "2025-06-11"


@pytest.mark.parametrize(
    "permit_type,years,applies,months,rule_id",
    [
        ("student", 0, False, None, "not-tied-to-employment"),
        ("family_based", 0, False, None, "not-tied-to-employment"),
        ("permanent", 0, False, None, "not-tied-to-employment"),
        ("eu_eea_citizen", 0, False, None, "not-tied-to-employment"),
        ("specialist_blue_card", None, True, 6, "specialist-or-long-term-work-six-months"),
        ("work_based", 1, True, 3, "work-based-three-months"),
        ("work_based", 3, True, 6, "specialist-or-long-term-work-six-months"),
    ],
)
def test_calculates_each_known_permit_type(permit_type, years, applies, months, rule_id):
    result = calculate_deadline(permit_type, years, JOB_END)
    assert result["applies"] is applies
    assert result["months"] == months
    assert result["rule_id"] == rule_id
    assert result["source_url"] == SOURCE_URL
    if months is None:
        assert result["deadline_date"] is None
    else:
        assert result["deadline_date"] is not None


@pytest.mark.parametrize(
    "years,months,expected",
    [
        (1.999, 3, date(2026, 4, 30)),
        (2, 3, date(2026, 4, 30)),
        (2.001, 6, date(2026, 7, 31)),
    ],
)
def test_two_year_boundary(years, months, expected):
    result = calculate_deadline("work_based", years, JOB_END)
    assert result["months"] == months
    assert result["deadline_date"] == expected


@pytest.mark.parametrize(
    "permit_type,years,start,expected",
    [
        ("work_based", 1, date(2026, 11, 30), date(2027, 2, 28)),
        ("specialist_blue_card", None, date(2026, 8, 31), date(2027, 2, 28)),
    ],
)
def test_month_end_deadlines_clamp_to_target_month(permit_type, years, start, expected):
    result = calculate_deadline(permit_type, years, start)
    assert result["deadline_date"] == expected


def test_not_sure_returns_both_possible_dates_with_rules_and_explanation():
    result = calculate_deadline("not_sure", None, JOB_END)
    assert result["applies"] is True
    assert result["deadline_date"] is None
    assert result["months"] is None
    assert result["rule_id"] is None
    assert "unclear" in result["explanation"]
    assert result["possible_dates"] == [
        {"months": 3, "deadline_date": date(2026, 4, 30), "rule_id": "work-based-three-months"},
        {"months": 6, "deadline_date": date(2026, 7, 31), "rule_id": "specialist-or-long-term-work-six-months"},
    ]


def test_work_based_without_duration_returns_both_possible_dates():
    result = calculate_deadline("work_based", None, JOB_END)
    assert [item["months"] for item in result["possible_dates"]] == [3, 6]

