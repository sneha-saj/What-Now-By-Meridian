# What Now? by Meridian

**Junction 2026 · Exa challenge**

You're a non-EU worker in Finland and you just lost your job. You type one sentence. *What Now?* asks you 2–3 quick tap-to-answer questions, then shows you:

1. **Your deadline**: how long you can stay to look for work. A plain rules engine works this out, not AI.
2. **This week's 3 things**, each with a source from migri.fi, kela.fi, infofinland.fi or tyomarkkinatori.fi.
3. **People who can help**, each with a message already drafted that you can copy and send.

Calm, plain language, one thing at a time.

## Run it

```bash
make dev
```

That one command installs everything on the first run (Python 3.11 venv + npm), copies `.env.example` to `.env`, and starts:

- backend → http://localhost:8000 (docs at `/docs`)
- frontend → http://localhost:3000

**No API keys? It still runs.** Every service falls back to mock data, and the UI shows a "Demo mode" note. Add `EXA_API_KEY` and `GEMINI_API_KEY` to `.env` for live mode.

Port busy? `make dev FRONTEND_PORT=3100 BACKEND_PORT=8100`. Other targets: `make test`, `make backend`, `make frontend`, `make clean`.

## Architecture

```
┌────────────┐   /api/*    ┌──────────────────────────┐
│  Web app   │ ──────────▶ │      Agent backend       │
│  Next.js   │  (proxied)  │        FastAPI           │
└────────────┘             └──────────┬───────────────┘
                                      │
              ┌───────────────────────┼────────────────────────┐
              ▼                       ▼                        ▼
      ┌──────────────┐        ┌──────────────┐         ┌──────────────┐
      │ Rules engine │        │    Gemini    │         │     Exa      │
      │  rules.py    │        │ extract facts│         │ official-site│
      │ deadlines,   │        │ write cited  │         │ search,      │
      │ no AI        │        │ steps, draft │         │ people &     │
      │              │        │ messages     │         │ companies    │
      └──────────────┘        └──────────────┘         └──────────────┘
```

| Endpoint | What it does |
|---|---|
| `POST /intake` | Gemini pulls facts out of the sentence. Code works out which facts are still missing and returns up to 3 questions. |
| `POST /plan` | The rules engine computes the deadline. Exa searches the 4 official domains. Gemini writes 3 steps that cite only those results, and any step without a real source is dropped. |
| `POST /referrals` | Exa company + people search (Websets is a TODO) finds contacts. Gemini drafts a message for each one. |

### Deadline rules (`backend/rules.py`)

| Situation | Job-seeking period |
|---|---|
| Work-based permit | 3 months from the last day of work |
| Specialist / EU Blue Card, or >2 years on a work-based permit | 6 months |
| Permanent resident, student, family-based permit, EU/Finnish citizen | Not applicable |

Simplified for the hackathon. This is not legal advice, and the UI always links to Migri.

### Layout

```
backend/
  main.py              FastAPI endpoints
  rules.py             deadline engine (no AI)
  questions.py         missing facts → tap-to-answer questions
  services/            gemini.py, exa_search.py, mocks.py
  integrations/        oxylabs.py, elevenlabs.py (stubs, not wired in)
  tests/               test_rules.py, test_api.py
frontend/
  app/page.tsx         single page
  components/ui.tsx    cards, chips, source chips
  lib/api.ts           typed API client
```

## Tech challenges used

- **Gemini API**: TODO: how we used it
- **OpenAI Codex**: TODO: how we used it
- **Oxylabs**: TODO: how we used it (stub: `backend/integrations/oxylabs.py`, flag `ENABLE_OXYLABS`)
- **ElevenLabs**: TODO: how we used it (stub: `backend/integrations/elevenlabs.py`, flag `ENABLE_ELEVENLABS`)

## License

MIT
