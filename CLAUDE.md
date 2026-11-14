# What Now? by Meridian — rules for AI assistants

## Commits & PRs
- Don't add AI attribution or co-author lines (e.g. `Co-Authored-By: Claude …`, "Generated with Claude Code") to commit messages or PR descriptions.
- Exception: mark commits where OpenAI Codex really did the work, so the "Tech challenges used" section stays honest. Put it in the subject, e.g. `rules engine + tests (built with Codex)`. Never add this to commits Codex didn't write.
- Write short, clear commit messages describing the change.
- Never commit .env or API keys.

## Project
- `backend/rules.py` is plain code, no AI. Any deadline change needs a matching test in `backend/tests/test_rules.py`.
- Every fact shown to the user needs a source (migri.fi, kela.fi, infofinland.fi, tyomarkkinatori.fi).
- Missing API keys must fall back to mocks; the demo always runs.
- No database.
- Test: `make test`. Run: `make dev`.

## API usage limits (Gemini free tier, limited Exa credits)
- Never call Gemini or Exa in loops, unbounded retries, or on file save/reload.
- Use `USE_MOCK=true` and the saved responses in `backend/mocks/` for frontend and UI work.
- Unit tests must mock Gemini and Exa; never call real APIs in tests (`backend/tests/conftest.py` forces mocks).
- Only make real API calls when explicitly asked, and keep it to 1–3 calls per test run.
- Always use the file caches for Exa and Gemini results; don't clear them unless asked.
- Use the fast/cheap Gemini model (`GEMINI_MODEL` in `.env`) unless told otherwise.
- Limit Exa results (max 5–10 per search); no deep research or Websets unless asked.
- On a rate limit (429), stop and tell the user; don't keep retrying.
- Never print or log API keys.
