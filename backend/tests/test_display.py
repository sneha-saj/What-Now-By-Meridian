"""Every roadmap and opportunity item has short display fields within limits, and /opportunities has counts."""

import os

os.environ["FORCE_MOCKS"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from models import Action, Incentive, OpportunitiesResponse, Source, shorten  # noqa: E402
from services import mocks  # noqa: E402

client = TestClient(main.app)


def _items(plan: dict, opp: dict | None = None):
    for key in ("this_week", "timeline", "plan_b"):
        yield from plan.get(key, [])
    if opp:
        for key in ("hidden_jobs", "people", "support", "events"):
            yield from opp[key]
        perks = opp["perks_and_support"]
        yield from perks["discounts"]
        yield from perks["incentives"]
        if perks.get("certificate"):
            yield perks["certificate"]


def _check(item):
    assert item["title_short"] and len(item["title_short"].split()) <= 6, item["title_short"]
    assert item["why_short"] and len(item["why_short"].split()) <= 12, item["why_short"]
    assert item["primary_action"]["label"] and item["primary_action"]["kind"]


def test_every_item_in_saved_examples_and_fallback_plan_has_short_fields(monkeypatch):
    monkeypatch.setattr(main, "get_live_check", lambda rule_id: {"rule_id": rule_id, "status": "verified",
                                                                 "checked_at": "2026-11-14T10:00:00+00:00", "evidence_snippet": ""})
    fallback = client.post("/plan", json={"facts": mocks.example_facts()}).json()
    saved_plan = mocks.example("plan")
    saved_opp = OpportunitiesResponse(**mocks.example("opportunities")).model_dump()
    from models import PlanResponse
    for item in [*_items(fallback), *_items(PlanResponse(**saved_plan).model_dump(), saved_opp)]:
        _check(item)


def test_long_text_is_shortened_in_code_and_gemini_short_text_is_kept():
    long = Action(title="Register as an unemployed jobseeker with the employment services of your city today",
                  why="Registering early keeps every one of your benefit options open from the very first day onwards",
                  how=[], sources=[Source(title="TMT", url="https://www.tyomarkkinatori.fi/en")])
    assert long.title_short == "Register as an unemployed jobseeker with…"
    assert len(long.why_short.split()) <= 12 and long.why_short.endswith("…")
    assert long.primary_action.label == "Go to tyomarkkinatori.fi" and long.primary_action.kind == "open_link"
    given = Action(title="x", why="y", how=[], sources=[], title_short="Register as a jobseeker", why_short="Keeps benefits open")
    assert (given.title_short, given.why_short, given.primary_action) == ("Register as a jobseeker", "Keeps benefits open", None)
    assert shorten("one two three", 6) == "one two three"


def test_incentive_short_why_is_the_caveat():
    inc = Incentive(name="Helsinki benefit", what_it_is="Pays employers", conditions_plain="3 months unemployed",
                    may_apply=False, caveat="May not work in time for your deadline.", source_url="https://hel.fi/b")
    assert inc.why_short == "May not work in time for your deadline."
    assert inc.primary_action.kind == "check_conditions"


def test_opportunities_counts_sections():
    body = OpportunitiesResponse(**mocks.example("opportunities")).model_dump()
    c = body["counts"]
    assert (c["hidden_jobs"], c["people"], c["support"], c["events"], c["certificate"], c["discounts"]) == (1, 1, 1, 1, 1, 1)
    assert c["total"] == 6
