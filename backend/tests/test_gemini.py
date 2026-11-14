"""Gemini wrapper: structured output and failure fallback, with a fake client."""

from types import SimpleNamespace

from services import gemini


class FakeModels:
    def __init__(self, parsed=None, text="{}", error=None):
        self.parsed, self.text, self.error, self.config = parsed, text, error, None

    def generate_content(self, model, contents, config):
        if self.error:
            raise self.error
        self.config = config
        return SimpleNamespace(parsed=self.parsed, text=self.text)


def test_extract_facts_requests_structured_output(monkeypatch):
    models = FakeModels(parsed=gemini.Extracted(citizenship_group="other", field="nurse"))
    monkeypatch.setattr(gemini, "_get_client", lambda: SimpleNamespace(models=models))
    out = gemini.extract_facts("I'm a nurse", "2026-11-14")
    assert out["citizenship_group"] == "other" and out["field"] == "nurse"
    assert models.config.response_schema is gemini.Extracted
    assert models.config.response_mime_type == "application/json"


def test_write_plan_parses_json_text_when_parsed_missing(monkeypatch):
    models = FakeModels(text='{"this_week": [], "timeline": [], "plan_b": []}')
    monkeypatch.setattr(gemini, "_get_client", lambda: SimpleNamespace(models=models))
    assert gemini.write_plan({}, {}, [{"id": "S1", "title": "t", "url": "u", "highlight": "h"}], "2026-11-14") == {
        "this_week": [], "timeline": [], "plan_b": []}
    assert models.config.response_schema is gemini.GeneratedPlan


def test_gemini_errors_return_none(monkeypatch):
    models = FakeModels(error=RuntimeError("quota"))
    monkeypatch.setattr(gemini, "_get_client", lambda: SimpleNamespace(models=models))
    assert gemini.extract_facts("x", "2026-11-14") is None


def test_no_key_returns_none(monkeypatch):
    monkeypatch.setattr(gemini, "_get_client", lambda: None)
    assert gemini.write_plan({}, {}, [], "2026-11-14") is None
