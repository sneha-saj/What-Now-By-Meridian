# What Now? by Meridian

**Junction 2026 · Exa challenge**

You're a non-EU worker in Finland and you just lost your job. You type one sentence. *What Now?* asks you 2–3 quick tap-to-answer questions, then shows you:

1. **What we know so far**: the facts we know about you, filled in as you answer, editable any time. Gemini picks up to 3 extra questions that make your steps specific.
2. **How long you can stay** to look for work. A plain rules engine works this out, not AI, and the rule is checked live against Migri's page.
3. **Your steps, in order** (Step 1, 2, 3…), each with a source from migri.fi, kela.fi, infofinland.fi or tyomarkkinatori.fi. Add info to any step and Exa and Gemini update that step and the ones after it.
4. **Perks and support** picked for your situation by plain rules: always the job search certificate, city discounts and employer hiring incentives (they only "may apply"); then, depending on your answers, your unemployment fund or other Kela support, free language courses and cheaper travel. Each item links to its source, with the page date, and "Why you see these" explains each pick.
5. **How we know this**: every rule, source and live check in one place.
6. **Ask**: ask a question in your own words; Exa answers from live sources, official ones for rules.
7. **Voice**: 🎤 talk instead of typing in any text box, and 🔊 "Listen" to the date and each step.

*Coming soon: **Find your way in**, growing companies and the people who can refer you, with a message ready to send.*

Calm, plain language, one thing at a time.

## Run it

```bash
make dev
```

The first run installs everything (Python 3.11 venv + npm) and copies `.env.example` to `.env`. Backend: http://localhost:8000 (docs at `/docs`). Frontend: http://localhost:3000.

Port busy? `make dev FRONTEND_PORT=3100 BACKEND_PORT=8100`. Other targets: `make test`, `make backend`, `make frontend`, `make clean`.

**API keys** (in `.env`). Without keys the app runs on mock data and shows "Demo mode".
- `EXA_API_KEY`, `GEMINI_API_KEY`: needed for live mode.
- `CONTEXT_DEV_API_KEY` (optional): reads whole official pages (Migri's rule page, perk pages). Cached 24h; falls back to Exa.
- `ELEVENLABS_API_KEY` (optional): voice typing and "Listen". Without it the buttons are hidden.

**Demo vs live.** Set `ACCESS_CODES=code1,code2`. Visitors get a free demo with no paid API calls. A valid code, entered under "Try the live version" or passed as `/start?code=code1`, unlocks live mode. If `ACCESS_CODES` is empty, everyone gets live mode.

**Deploy.** Every push to `main` deploys to Modal through [GitHub Actions](.github/workflows/deploy-modal.yml). The workflow needs these secrets: `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`, `EXA_API_KEY`, `GEMINI_API_KEY`, `ACCESS_CODES`. To deploy by hand, run `backend/.venv/bin/modal deploy frontend/modal_app.py`. Live at [what-now-by-meridian--site.us-east.modal.run](https://what-now-by-meridian--site.us-east.modal.run).

## Architecture

```
┌────────────┐   /api/*    ┌──────────────────────────┐
│  Web app   │ ──────────▶ │      Agent backend       │
│  Next.js   │  (proxied)  │        FastAPI           │
└────────────┘             └─────────────┬────────────┘
                                         │
       ┌──────────────┬──────────────┬───┴──────────┬──────────────┐
       ▼              ▼              ▼              ▼              ▼
┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
│   Rules    │ │   Gemini   │ │    Exa     │ │Context.dev │ │ ElevenLabs │
│   engine   │ │  extract   │ │  official  │ │ read whole │ │   voice    │
│  rules.py  │ │facts, cited│ │search, perks│ │  official  │ │  typing,   │
│ deadlines, │ │steps, sort │ │ ask, rule  │ │   pages    │ │   Listen   │
│   no AI    │ │   perks    │ │   checks   │ │ (optional) │ │ (optional) │
└────────────┘ └────────────┘ └────────────┘ └────────────┘ └────────────┘
```

| Endpoint | What it does |
|---|---|
| `POST /intake` | Gemini pulls facts out of the sentence. Code works out which facts are still missing and returns up to 3 questions. |
| `POST /plan` | The rules engine computes the deadline. Exa searches the 4 official domains. Gemini writes 3 steps that cite only those results, and any step without a real source is dropped. Also returns the timeline and Plan B permits. |
| `POST /steps/update` (+ `/stream`) | You add info to a step; Exa and Gemini rewrite that step and the ones after it. |
| `POST /chat` (+ `/stream`) | The guided flow: questions one at a time, then the deadline, then this week's 3 steps. |
| `POST /opportunities` (+ `/stream`) | Perks and support: Exa searches official and city sites, Gemini sorts the results, code keeps only sourced items. |
| `POST /ask` | Exa answers a question with citations; rules questions use only the official domains. |
| `GET /rules` | The deadline rules, their latest live check against Migri, and the sources used. |
| `POST /voice/transcribe` | Voice typing: a short recording in, its text out (ElevenLabs). |
| `POST /voice/speak` | Listen: text in, MP3 out (ElevenLabs, cached 7 days). |
| `GET /health` | Health check. |

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
  countries/           country config (finland.py)
  questions.py         missing facts → tap-to-answer questions
  plan_b.py            which Plan B permits fit (plain code)
  opportunities.py     Perks and support
  ask.py               /ask helpers: on topic? about rules? which step?
  live_check.py        daily check of the rules against Migri's page
  sources_log.py       every source used, for "How we know this"
  activity.py          live Exa/Gemini activity streamed to the UI
  limits.py            pauses a paid API after a 429 and uses fallbacks
  filecache.py         JSON file cache for Exa and Gemini
  services/            gemini.py, exa_search.py, mocks.py
  integrations/        context_dev.py, elevenlabs.py (voice typing and Listen)
  mocks/               saved responses for demo mode and tests
  tests/               pytest suite (rules, API, access, voice, …)
frontend/
  app/                 page.tsx (home), start/, how-we-know/, api/ (proxy to backend)
  components/          Steps, Opportunities, AskPanel, Voice, AccessCode, …
  lib/api.ts           typed API client
```

## Main challenge
- [x] **Exa – The Internet Butler / Your Personal Assistant**: Exa finds and reads the facts: official sites (migri.fi, kela.fi, infofinland.fi, tyomarkkinatori.fi), full page contents with highlights, perks and support on city sites, answers to questions, and live checks of the rule sources.

## Tech challenges
- [x] **Gemini API (Google DeepMind)**: reads your first message and picks the questions that matter for you; writes your steps only from the sources Exa found (every step must cite one); rewrites steps when you add info; checks daily that Migri's page still matches our stored rules; sorts perks and judges whether employer incentives "may apply". The date itself always comes from plain code, not AI.
- [x] **OpenAI Codex**: used to build the Finland country config, rules engine + tests, live rule check and the "How we know this" page (see commits marked "codex:" or "[codex]" and the related pull requests).
- [x] **Context.dev**: reads whole official pages for exact details: Migri's rule page for the live rule check, and the perk pages (certificate, discounts, incentives) with a JSON Schema. Shown in the app as "Read from the page by Context.dev"; Exa remains the fallback.
- [x] **ElevenLabs**: 🎤 voice typing in every free-text box (speech to text, `scribe_v3`) and 🔊 "Listen" on the date and each step (text to speech, `eleven_flash_v2_5`, cached). For people who are stressed, reading in a second language, or find listening easier. Needs `ELEVENLABS_API_KEY`; without it the buttons are hidden. Recordings go to ElevenLabs and are not stored by us; the app says so next to the mic.
- [x] **Modal**: hosts the public Next.js site and its FastAPI backend, with a separate API deployment available.

## License

MIT
