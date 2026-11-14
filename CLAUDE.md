# What Now? by Meridian — rules for AI assistants

## Commits & PRs
- Don't add AI attribution or co-author lines (e.g. `Co-Authored-By: Claude …`, "Generated with Claude Code") to commit messages or PR descriptions.
- Exception: mark commits where OpenAI Codex really did the work, so the "Tech challenges used" section stays honest. Put it in the subject, e.g. `rules engine + tests (built with Codex)`. Never add this to commits Codex didn't write.

## Project
- `backend/rules.py` is plain code, no AI. Any deadline change needs a matching test in `backend/tests/test_rules.py`.
- Every fact shown to the user needs a source (migri.fi, kela.fi, infofinland.fi, tyomarkkinatori.fi).
- Missing API keys must fall back to mocks; the demo always runs.
- No database.
- Test: `make test`. Run: `make dev`.
