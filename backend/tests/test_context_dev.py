"""Context.dev wrapper and its use in Perks and support. httpx is faked: no live calls."""

from datetime import date

import pytest

import limits
import opportunities as opps
from integrations import context_dev
from models import Facts


class FakeResponse:
    def __init__(self, status: int, body: dict):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


def ok_json(data, **extra):
    return {"url": "https://www.hel.fi/x", "json": {"requested": True, "success": True, "data": data},
            "markdown": {"requested": False, "success": None, "data": None}, **extra}


@pytest.fixture
def calls(monkeypatch):
    sent = []
    monkeypatch.setattr(context_dev.config, "context_key", lambda: "ctxt_secret_test")

    def post(url, json, headers, timeout):
        sent.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return sent_response[0]
    sent_response = [FakeResponse(200, ok_json({"discounts": [{"name": "Swimming", "discount": "50% off"}]}))]
    monkeypatch.setattr(context_dev.httpx, "post", post)
    return {"sent": sent, "respond": lambda r: sent_response.__setitem__(0, r)}


def test_request_follows_the_docs_and_settings(calls):
    data = context_dev.extract_json("https://www.hel.fi/x", {"type": "object"}, "only what the page says", purpose="t")
    assert data == {"discounts": [{"name": "Swimming", "discount": "50% off"}]}
    req = calls["sent"][0]
    assert req["url"] == "https://api.context.dev/v1/web/scrape"
    assert req["headers"]["Authorization"] == "Bearer ctxt_secret_test"
    body = req["json"]
    assert body["formats"] == {"json": True}
    assert body["jsonParams"] == {"schema": {"type": "object"}, "instructions": "only what the page says"}
    assert body["maxAgeMs"] == 86_400_000 and body["timeoutOpts"] == {"milliseconds": 30_000, "behavior": "return-partial"}
    assert "zdr" not in body and req["timeout"] > 30


def test_results_are_cached_for_a_day(calls):
    for _ in range(2):
        context_dev.extract_json("https://www.hel.fi/x", {"type": "object"}, "i", purpose="t")
    assert len(calls["sent"]) == 1


def test_no_key_means_no_call(monkeypatch):
    monkeypatch.setattr(context_dev.config, "context_key", lambda: None)
    monkeypatch.setattr(context_dev.httpx, "post", lambda *a, **k: pytest.fail("called without a key"))
    assert context_dev.extract_json("https://x.fi", {"type": "object"}, "i", purpose="t") is None


@pytest.mark.parametrize("status", [429, 402])
def test_rate_limit_or_no_credits_pauses_without_retrying(calls, status):
    calls["respond"](FakeResponse(status, {"error_code": "RATE_LIMITED"}))
    assert context_dev.extract_json("https://x.fi/a", {"type": "object"}, "i", purpose="t") is None
    assert limits.paused("Context.dev")
    assert context_dev.extract_json("https://x.fi/b", {"type": "object"}, "i", purpose="t") is None
    assert len(calls["sent"]) == 1  # paused: the second call never went out


def test_failed_or_empty_outputs_return_nothing(calls):
    calls["respond"](FakeResponse(200, {"json": {"requested": True, "success": False, "error_code": "WEBSITE_BLOCKED",
                                                 "message": "blocked", "data": None}}))
    assert context_dev.extract_json("https://x.fi", {"type": "object"}, "i", purpose="t") is None
    calls["respond"](FakeResponse(500, {"error_code": "INTERNAL"}))
    assert context_dev.extract_json("https://x.fi/2", {"type": "object"}, "i", purpose="t") is None
    assert not limits.paused("Context.dev")  # a normal error doesn't pause


def test_partial_response_uses_what_succeeded(calls):
    calls["respond"](FakeResponse(200, ok_json({"discounts": []}, isPartial=True,
                                               screenshot={"requested": True, "success": False, "data": None})))
    assert context_dev.extract_json("https://x.fi", {"type": "object"}, "i", purpose="t") == {"discounts": []}


# ---------- in Perks and support ----------

FACTS = Facts(citizenship_group="other", permit_type="work_based", years_on_work_permit=1,
              job_end_date=date(2026, 11, 1), city="Helsinki", field="cook")
RAW = {
    "perks:certificate": [{"title": "Certificate", "url": "https://tyomarkkinatori.fi/cert", "published": "2026-10-01", "highlight": "x", "purpose": "perks"}],
    "perks:discounts": [{"title": "Discounts", "url": "https://www.hel.fi/discounts", "published": "2026-09-01", "highlight": "x", "purpose": "perks"}],
    "perks:incentives": [{"title": "Helsinki benefit", "url": "https://www.hel.fi/benefit", "published": None, "highlight": "short", "purpose": "perks"}],
}
READ = {
    "https://tyomarkkinatori.fi/cert": {"how_to_get": "Log in to Job Market Finland and download it under E-services."},
    "https://www.hel.fi/discounts": {"discounts": [{"name": "Swimming halls", "discount": "€2.50 instead of €6", "proof_needed": "Job search certificate"},
                                                   {"name": "No price stated", "discount": None}]},
    "https://www.hel.fi/benefit": {"incentives": [{"name": "Helsinki benefit", "conditions": "Unemployed for 3 months"}]},
}


def test_perks_use_exact_details_from_the_pages_and_say_so(monkeypatch):
    seen_rows = {}
    monkeypatch.setattr(opps.context_dev, "available", lambda: True)
    monkeypatch.setattr(opps.context_dev, "extract_json", lambda url, schema, instr, purpose: READ[url])
    monkeypatch.setattr(opps.exa_search, "search_opportunities", lambda *a: {k: [dict(r) for r in v] for k, v in RAW.items()})

    def gemini(facts, months, rows, today):
        seen_rows["incentive"] = next(r for r in rows if r["section"] == "perks:incentives")["highlight"]
        return {"certificate": None, "discounts": [{"row_id": "R2", "name": "Swimming halls", "discount": "cheap", "proof_needed": "x"}],
                "incentives": [{"row_id": "R3", "name": "Helsinki benefit", "what_it_is": "Pays employers",
                                "conditions_plain": "Unemployed for 3 months", "may_apply": True, "caveat": ""}]}
    monkeypatch.setattr(opps.gemini, "write_opportunities", gemini)

    p = opps.build(FACTS, 3, date(2026, 11, 14)).perks_and_support
    assert p.certificate.read_by == "context.dev" and "E-services" in p.certificate.how_to_get
    assert [(d.discount, d.read_by) for d in p.discounts] == [("€2.50 instead of €6", "context.dev")]  # exact, deduplicated
    assert p.discounts[0].source_url == "https://www.hel.fi/discounts" and p.discounts[0].source_date == "2026-09-01"
    assert "Context.dev" in seen_rows["incentive"] and "3 months" in seen_rows["incentive"]
    assert p.incentives[0].read_by == "context.dev" and "may not work in time" in p.incentives[0].caveat


def test_without_context_dev_perks_work_as_before(monkeypatch):
    monkeypatch.setattr(opps.context_dev, "extract_json", lambda *a, **k: pytest.fail("Context.dev called without a key"))
    monkeypatch.setattr(opps.exa_search, "search_opportunities", lambda *a: {k: [dict(r) for r in v] for k, v in RAW.items()})
    monkeypatch.setattr(opps.gemini, "write_opportunities", lambda *a: {
        "certificate": {"row_id": "R1", "how_to_get": "Download it"}, "discounts": [], "incentives": []})
    p = opps.build(FACTS, 3, date(2026, 11, 14)).perks_and_support
    assert p.certificate.how_to_get == "Download it" and p.certificate.read_by is None
