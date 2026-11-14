# What Now? by Meridian

**Junction 2026 · Exa challenge**

You're a non-EU worker in Finland and you just lost your job. You type one sentence. *What Now?* asks you 2–3 quick tap-to-answer questions, then shows you:

1. **What we know so far**: the facts we know about you, filled in as you answer, editable any time. Gemini picks up to 3 extra questions that make your steps specific.
2. **How long you can stay** to look for work. A plain rules engine works this out, not AI, and the rule is checked live against Migri's page.
3. **Your steps, in order** (Step 1, 2, 3…), each with a source from migri.fi, kela.fi, infofinland.fi or tyomarkkinatori.fi. Add info to any step and Exa and Gemini update that step and the ones after it.
4. **Perks and support** picked for your situation by plain rules: always the job search certificate, city discounts and employer hiring incentives (they only "may apply"); then, depending on your answers, your unemployment fund or other Kela support, free language courses and cheaper travel. Each item links to its source, with the page date, and "Why you see these" explains each pick.
5. **How we know this**: every rule, source and live check in one place.
6. **Ask**: ask a question in your own words; Exa answers from live sources, official ones for rules.

*Coming soon: **Find your way in**, growing companies and the people who can refer you, with a message ready to send.*

Calm, plain language, one thing at a time.

## Run it

```bash
make dev
```

That one command installs everything on the first run (Python 3.11 venv + npm), copies `.env.example` to `.env`, and starts:

- backend → http://localhost:8000 (docs at `/docs`)
- frontend → http://localhost:3000

**No API keys? It still runs.** Every service falls back to mock data, and the UI shows a "Demo mode" note. Add `EXA_API_KEY` and `GEMINI_API_KEY` to `.env` for live mode.

Optional: add `CONTEXT_DEV_API_KEY` to `.env` (get one at context.dev/dashboard/api-keys) so Context.dev's Scrape API reads whole official pages where exact details matter:
- **Migri's rule page** for the daily live rule check (shared across rules, once a day).
- **Perks and support**: the top page for each perk is read with a JSON Schema, so the certificate steps, each discount with its price and the proof you need, and each incentive's conditions come from the page itself. These items show "Read from the page by Context.dev".

It's called with plain HTTP from `backend/integrations/context_dev.py`: cached 24h, `maxAgeMs` 1 day, 30 s deadline with partial results, no retries, paused on 429/402. Only the public page URL is sent, never your answers. If it fails, Exa's summary is used. Try one page by hand (one live call): `cd backend && .venv/bin/python -m integrations.context_dev https://migri.fi/en/home`

For Modal deployment, `.env` has placeholders for `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET`. Modal uses this token pair to authenticate its CLI; these values are not needed to run the app locally, and Modal does not automatically read this project's `.env`. You can also configure the CLI with `modal setup`.

To deploy on Modal, install its CLI in `backend/.venv` (`backend/.venv/bin/pip install modal`) and sign in with `backend/.venv/bin/modal setup` or provide both Modal token variables. Deploy the public site with `backend/.venv/bin/modal deploy frontend/modal_app.py`. The site bundles Next.js and FastAPI in one Modal container, so its `/api` requests stay local. The deploy script sends Exa, Gemini, Context.dev, and ElevenLabs keys plus access codes from local `.env` or CI environment variables as a Modal Secret. The public site is at [what-now-by-meridian--site.us-east.modal.run](https://what-now-by-meridian--site.us-east.modal.run). The API can also be deployed separately with `backend/.venv/bin/modal deploy backend/modal_app.py` at [what-now-by-meridian--api.us-east.modal.run](https://what-now-by-meridian--api.us-east.modal.run).

Pushes to `main` automatically deploy both Modal apps through [the GitHub Actions workflow](.github/workflows/deploy-modal.yml). Configure repository Actions secrets named `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`, `EXA_API_KEY`, `GEMINI_API_KEY`, and `ACCESS_CODES`; `CONTEXT_DEV_API_KEY` and `ELEVENLABS_API_KEY` are optional. The workflow checks the public site and API after deployment. Manual `modal deploy` remains available for urgent fixes.

**Live mode only for judges (optional).** Set `ACCESS_CODES=code1,code2` (in `.env` locally, and as a Modal secret
when hosted). Then anyone with the link gets a free **demo mode**: no paid API calls. The date still comes from the
rules engine, the steps from our checked saved guide, and the app says clearly that it's a demo. Someone with a code
(typed under "Judge? Enter access code" on the first page, or via a link like `/start?code=code1`) gets the full live
version. The code stays in that browser and is checked on the server. Leave it empty and everyone gets live mode.

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
      │ no AI        │        │ steps, sort  │         │ perks, ask,  │
      │              │        │ perks        │         │ rule checks  │
      └──────────────┘        └──────────────┘         └──────────────┘
```

| Endpoint | What it does |
|---|---|
| `POST /intake` | Gemini pulls facts out of the sentence. Code works out which facts are still missing and returns up to 3 questions. |
| `POST /plan` | The rules engine computes the deadline. Exa searches the 4 official domains. Gemini writes 3 steps that cite only those results, and any step without a real source is dropped. |
| `POST /chat` (+ `/stream`) | The guided flow: questions one at a time, then the deadline, then this week's 3 steps. |
| `POST /opportunities` (+ `/stream`) | Perks and support: Exa searches official and city sites, Gemini sorts the results, code keeps only sourced items. |
| `POST /ask` | Exa answers a question with citations; rules questions use only the official domains. |
| `GET /rules` | The deadline rules, their latest live check against Migri, and the sources used. |

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
  opportunities.py     Perks and support
  integrations/        context_dev.py, elevenlabs.py (voice typing and Listen)
  tests/               test_rules.py, test_api.py
frontend/
  app/page.tsx         single page
  components/ui.tsx    cards, chips, source chips
  lib/api.ts           typed API client
```

## Main challenge
- [x] **Exa – The Internet Butler / Your Personal Assistant**: Exa finds and reads the facts: official sites (migri.fi, kela.fi, infofinland.fi, tyomarkkinatori.fi), full page contents with highlights, perks and support on city sites, answers to questions, and live checks of the rule sources.

## Tech challenges
- [x] **Gemini API (Google DeepMind)**: reads your first message and picks the questions that matter for you; writes your steps only from the sources Exa found (every step must cite one); rewrites steps when you add info; checks daily that Migri's page still matches our stored rules; sorts perks and judges whether employer incentives "may apply". The date itself always comes from plain code, not AI.
- [x] **OpenAI Codex**: used to build the Finland country config, rules engine + tests, live rule check and the "How we know this" page (see commits marked "codex:" or "[codex]" and the related pull requests).
- [x] **Context.dev**: reads whole official pages for exact details: Migri's rule page for the live rule check, and the perk pages (certificate, discounts, incentives) with a JSON Schema. Shown in the app as "Read from the page by Context.dev"; Exa remains the fallback.
- [ ] **Oxylabs Web API**: not used. It was planned for company career pages, which went away with job search.
- [x] **ElevenLabs**: 🎤 voice typing in every free-text box (speech to text, `scribe_v3`) and 🔊 "Listen" on the date and each step (text to speech, `eleven_flash_v2_5`, cached). For people who are stressed, reading in a second language, or find listening easier. Needs `ELEVENLABS_API_KEY`; without it the buttons are hidden. Recordings go to ElevenLabs and are not stored by us; the app says so next to the mic.
- [ ] **Gemma (Google DeepMind)**: (idea) strip personal details before data leaves the device.
- [x] **Modal**: hosts the public Next.js site and its FastAPI backend, with a separate API deployment available.
- [ ] **MongoDB Atlas (MLH)**: (idea) save the user's plan and progress.

Only ticked items are used in the current version. We tick items when they're actually integrated.

## License

MIT
