# What Now? API

Backend: FastAPI in `backend/`. Run `make dev`, then open the interactive docs at
http://localhost:8000/docs (every endpoint has the examples below built in).

**Example persona** used throughout: a restaurant worker from India on a work-based permit, 1 year in
Finland, living in Helsinki, whose job ended on 1 November 2026.

The example responses are saved in `backend/mocks/` and are what the API returns when `USE_MOCK=true`.
Official sources in them are real pages. Sample perks are clearly marked samples (`example.com`), because we
don't put invented offers in front of users as real.

**Short display fields.** Every roadmap item (`this_week`, `timeline`, `plan_b`) and every opportunity item has
`title_short` (max 6 words), `why_short` (max 12 words) and `primary_action` (`kind`: `open_link` or
`check_conditions`, `label`, `url`) for compact cards. Gemini writes them; code enforces the limits
and derives them from the long fields when missing. Long fields (`how`, `steps`, `highlight`, `eligibility_note`)
are for the expanded view. `/opportunities` also returns `counts` (`certificate`, `discounts`, `incentives`, `total`).

Every response has `mock: true` when a fallback was used (no API key, or a call failed). The demo always runs.

| Endpoint | Purpose |
| --- | --- |
| `POST /intake` | Turn the user's sentence into facts; ask up to 3 questions the deadline still needs |
| `POST /plan` | Deadline, 3 actions for this week, a timeline and plan B, all with official sources |
| `GET /rules` | The deadline rules, their latest live check against Migri, and trusted domains |
| `POST /chat` | Guided chat: the same steps, one message at a time, with a live "What we know so far" card |
| `POST /chat/stream` | Same as `/chat`, streamed with live progress, Exa activity and partial results |
| `POST /opportunities` (+ `/stream`) | Perks and support: job search certificate, city discounts, employer incentives, all from live Exa sources |
| `POST /steps/update` (+ `/stream`) | Add info to one step; that step and the ones after it are rewritten live |
| `POST /ask` | Ask a question; Exa's Answer endpoint replies with sources |
| `GET /health` | Which integrations have keys configured |

---

## POST /intake

Gemini extracts facts from free text (structured JSON output). Facts are merged with `answers` to
earlier questions; answers win. `missing_questions` only covers what the deadline needs
(citizenship group, permit type, years on a work permit, job end date), at most 3, with "Not sure"
where it makes sense. It never asks for permit numbers or passport details.

**Input**

| Field | Type | Notes |
| --- | --- | --- |
| `text` | string | What the user wrote |
| `answers` | object | Optional. Answers to earlier questions, keyed by question `id` |

**Output**: `facts`, `missing_questions` (`id`, `question`, `kind`: `choice` or `date`, `options`: `value` + `label`), `mock`.
If the job was outside Finland: `out_of_scope: true`, `message`, `link` instead of facts.

Questions come from a fixed `QUESTION_BANK` in the Finland config (`backend/countries/finland.py`); code picks the
next missing field, so the wording and answers are always checked. The order is:

1. `lost_job`, only if the message doesn't say.
2. `REQUIRED_FIELDS`, what the deadline needs: citizenship group, permit type, years on a work permit, job end date.
3. Up to 3 **personal questions** (`PERSONAL_QUESTIONS`) that make the steps specific: `city`, `field`,
   `unemployment_fund`, `registered_jobseeker`, `studied_in_finland`, `family_in_finland`. In the same call that
   reads the message, Gemini picks which of these matter for this person (`useful_questions`); code keeps only ids
   from the list, max 3, and stores them as `facts.to_ask` so later taps need no Gemini call. Anything the message
   already answered is skipped. Without Gemini, `DEFAULT_PERSONAL` is asked (city, field, unemployment fund).
   City and work have "Skip" (stored as `""`, not asked again).

The steps then use these answers: the Exa searches follow the city, field, fund and registration, and Gemini is
told not to say "register" to someone already registered and to point fund members to their fund, others to Kela.
`/intake` only returns the deadline questions. Approximate date answers arrive as `about:YYYY-MM-DD` and set
`job_end_date_approximate`; the deadline then has `deadline_is_approximate: true`.

Facts: `citizenship_group` (`eu_eea` / `other` / `unknown`), `citizenship_country`, `permit_type`,
`years_on_work_permit` (number, or `under_2` / `over_2` / `not_sure`), `job_end_date`, `city`, `field`,
`studied_in_finland`, `family_in_finland`, `unemployment_fund` (`yes` / `no` / `not_sure`),
`registered_jobseeker` (`yes` / `no`), `to_ask` (the personal questions picked for this person).

### Example: everything known

Request:
```json
{
  "text": "I'm from India and worked in a restaurant in Helsinki for a year on a work permit. My job ended on 1 November.",
  "answers": {}
}
```

Response:
```json
{
  "facts": {
    "citizenship_group": "other",
    "citizenship_country": "India",
    "permit_type": "work_based",
    "years_on_work_permit": 1,
    "job_end_date": "2026-11-01",
    "city": "Helsinki",
    "field": "restaurant worker",
    "studied_in_finland": false,
    "family_in_finland": false
  },
  "missing_questions": [],
  "out_of_scope": false,
  "mock": true
}
```

### Example: questions still needed

Request:
```json
{
  "text": "I'm from India and lost my restaurant job in Helsinki.",
  "answers": {}
}
```

Response:
```json
{
  "facts": {
    "citizenship_group": "other",
    "citizenship_country": "India",
    "city": "Helsinki",
    "field": "restaurant worker"
  },
  "missing_questions": [
    {
      "id": "permit_type",
      "question": "What kind of residence permit do you have?",
      "kind": "choice",
      "options": [
        {
          "value": "work_based",
          "label": "Work-based"
        },
        {
          "value": "specialist_blue_card",
          "label": "Specialist / EU Blue Card"
        },
        {
          "value": "student",
          "label": "Student"
        },
        {
          "value": "family_based",
          "label": "Family-based"
        },
        {
          "value": "permanent",
          "label": "Permanent"
        },
        {
          "value": "not_sure",
          "label": "Not sure"
        }
      ]
    },
    {
      "id": "job_end_date",
      "question": "When was (or is) your last day of work?",
      "kind": "date",
      "options": [
        {
          "value": "2026-11-14",
          "label": "Today"
        },
        {
          "value": "2026-11-07",
          "label": "About a week ago"
        },
        {
          "value": "2026-10-15",
          "label": "About a month ago"
        }
      ]
    }
  ],
  "out_of_scope": false,
  "mock": true
}
```

### Example: job outside Finland

Request:
```json
{
  "text": "I lost my job in Sweden last week.",
  "answers": {}
}
```

Response:
```json
{
  "missing_questions": [],
  "out_of_scope": true,
  "message": "What Now? only covers jobs in Finland. If your job was in another country, check that country's official services. InfoFinland explains unemployment in Finland.",
  "link": "https://www.infofinland.fi/en/work-and-enterprise/unemployment",
  "mock": true
}
```

---

## POST /plan

1. The rules engine (`rules.calculate_deadline`, plain code) computes the deadline from the facts.
2. The live check confirms the rule against the official Migri page, judging meaning rather than exact wording.
   The date is always shown. If the page seems to say something different (`mismatch`), a calm `warning`
   is added; if the check couldn't run (`error`), a neutral "Couldn't check right now" note is added.
3. Exa searches only the trusted domains (preferring pages updated after June 2025) for: registering
   as a jobseeker, unemployment benefits, alternative permits for this person, and labour-shortage sectors.
4. Gemini writes the plan from those pages only. Every action must cite at least one real source;
   if the sources don't cover something, it says "Check with Migri or your union".

**Input**: `{"facts": {...}}`, the facts from `/intake`.

**Output**

| Field | Notes |
| --- | --- |
| `deadline` | `status` (`ok` / `not_applicable` / `needs_info` / `unclear`), `explanation`, `months`, `deadline_date` (always set when the rule applies and the job end date is known), `days_left`, `possible_dates` (when the permit or years are unclear), `rule_in_force_since`, `source`, `verified`, `check_status` (`verified` / `mismatch` / `error` / `none`), `live_checks`, `warning`, `warning_link` |
| `this_week` | Exactly 3 actions: `title`, `why` (one calm sentence), `how` (short steps), `sources` (`title`, `url`, `highlight`) |
| `timeline` | Steps back from the deadline: Week 1, 2, 4, 8, Final weeks. Each has `steps` and `sources` |
| `plan_b` | Permits that fit this person, chosen by plain code (new employer; job-seeker permit if they studied in Finland; family-based if they have family here; entrepreneur): `id`, `option`, `who_it_fits`, `why`, `latest_start_date` (the deadline), `sources`. Options without a source are dropped |
| `plan_b_note` | Plain-language note when no option fits or none is needed |
| `disclaimer` | Not legal advice |

### Example

Request:
```json
{
  "facts": {
    "citizenship_group": "other",
    "citizenship_country": "India",
    "permit_type": "work_based",
    "years_on_work_permit": 1,
    "job_end_date": "2026-11-01",
    "city": "Helsinki",
    "field": "restaurant worker",
    "studied_in_finland": false,
    "family_in_finland": false
  }
}
```

Response:
```json
{
  "deadline": {
    "status": "ok",
    "explanation": "If employment ends early, a work-based permit held for 2 years or less has a 3-month protection period to find a new job. Based on your last day of work, the date is 2027-02-01.",
    "applies": true,
    "months": 3,
    "deadline_date": "2027-02-01",
    "days_left": 79,
    "possible_dates": [],
    "missing": [],
    "rule_id": "work-based-three-months",
    "source": {
      "title": "Migri – Changes to work-based residence permits",
      "url": "https://migri.fi/en/-/changes-to-work-based-residence-permits-protection-period-for-unemployment-and-new-notification-obligation-for-employers?languageId=en_US",
      "highlight": null
    },
    "verified": true,
    "live_checks": [
      {
        "rule_id": "work-based-three-months",
        "status": "verified",
        "checked_at": "2026-11-14T09:00:00+00:00",
        "evidence_snippet": "Example check result: the page states a 3-month period for permits held 2 years or less."
      }
    ],
    "warning": null,
    "warning_link": null,
    "check_status": "verified"
  },
  "this_week": [
    {
      "title": "Register as an unemployed jobseeker",
      "why": "Registering early keeps your benefit options open.",
      "how": [
        "Open Job Market Finland (Työmarkkinatori)",
        "Log in with your online banking codes",
        "Register as an unemployed jobseeker"
      ],
      "sources": [
        {
          "title": "Job Market Finland (Työmarkkinatori)",
          "url": "https://tyomarkkinatori.fi/en",
          "highlight": null
        },
        {
          "title": "InfoFinland – Unemployment",
          "url": "https://www.infofinland.fi/en/work-and-enterprise/unemployment",
          "highlight": null
        }
      ]
    },
    {
      "title": "Check what support you can get",
      "why": "Knowing your income for the next months makes planning calmer.",
      "how": [
        "Read Kela's unemployment page",
        "If you belong to an unemployment fund, ask about earnings-related allowance"
      ],
      "sources": [
        {
          "title": "Kela – Unemployment",
          "url": "https://www.kela.fi/unemployment",
          "highlight": null
        },
        {
          "title": "InfoFinland – Unemployment",
          "url": "https://www.infofinland.fi/en/work-and-enterprise/unemployment",
          "highlight": null
        }
      ]
    },
    {
      "title": "Note your deadline: 1 February 2027",
      "why": "You have 3 months to find a new job under your current permit.",
      "how": [
        "Write the date down",
        "If anything about your permit is unclear, check with Migri or your union"
      ],
      "sources": [
        {
          "title": "Migri – Changes to work-based residence permits",
          "url": "https://migri.fi/en/-/changes-to-work-based-residence-permits-protection-period-for-unemployment-and-new-notification-obligation-for-employers?languageId=en_US",
          "highlight": null
        }
      ]
    }
  ],
  "timeline": [
    {
      "week": "Week 1",
      "steps": [
        "Register as a jobseeker",
        "Check Kela support"
      ],
      "sources": [
        {
          "title": "Job Market Finland (Työmarkkinatori)",
          "url": "https://tyomarkkinatori.fi/en",
          "highlight": null
        },
        {
          "title": "Kela – Unemployment",
          "url": "https://www.kela.fi/unemployment",
          "highlight": null
        }
      ]
    },
    {
      "week": "Week 2",
      "steps": [
        "Update your CV and apply for restaurant and kitchen roles"
      ],
      "sources": [
        {
          "title": "Job Market Finland (Työmarkkinatori)",
          "url": "https://tyomarkkinatori.fi/en",
          "highlight": null
        }
      ]
    },
    {
      "week": "Week 4",
      "steps": [
        "Review progress; check other permit options with Migri or your union"
      ],
      "sources": [
        {
          "title": "Migri – Changes to work-based residence permits",
          "url": "https://migri.fi/en/-/changes-to-work-based-residence-permits-protection-period-for-unemployment-and-new-notification-obligation-for-employers?languageId=en_US",
          "highlight": null
        }
      ]
    },
    {
      "week": "Week 8",
      "steps": [
        "If you have an offer, prepare your new permit application"
      ],
      "sources": [
        {
          "title": "Migri – Changes to work-based residence permits",
          "url": "https://migri.fi/en/-/changes-to-work-based-residence-permits-protection-period-for-unemployment-and-new-notification-obligation-for-employers?languageId=en_US",
          "highlight": null
        }
      ]
    },
    {
      "week": "Final weeks",
      "steps": [
        "Apply for a new permit before 1 February 2027 if you have a new job"
      ],
      "sources": [
        {
          "title": "Migri – Changes to work-based residence permits",
          "url": "https://migri.fi/en/-/changes-to-work-based-residence-permits-protection-period-for-unemployment-and-new-notification-obligation-for-employers?languageId=en_US",
          "highlight": null
        }
      ]
    }
  ],
  "plan_b": [
    {
      "id": "new_employer",
      "option": "A new work-based residence permit",
      "who_it_fits": "Anyone who gets a job offer from a new employer before the deadline.",
      "why": "If a new employer hires you, you can apply for a new work-based permit. Check the conditions on Migri's site.",
      "latest_start_date": "2027-02-01",
      "sources": [
        {
          "title": "Migri – Finnish Immigration Service",
          "url": "https://migri.fi/en/home",
          "highlight": null
        }
      ]
    },
    {
      "id": "entrepreneur",
      "option": "Residence permit for an entrepreneur",
      "who_it_fits": "People who want to start or run their own business in Finland.",
      "why": "If you want to start your own business, for example in food, Migri has a separate permit. Check the conditions first.",
      "latest_start_date": "2027-02-01",
      "sources": [
        {
          "title": "Migri – Finnish Immigration Service",
          "url": "https://migri.fi/en/home",
          "highlight": null
        }
      ]
    }
  ],
  "disclaimer": "This is general guidance based on official Finnish sources, not legal advice. Rules can change: confirm your situation with Migri, Kela or your union.",
  "mock": true
}
```

---

## GET /rules

The deadline rules from the Finland country config (`backend/countries/finland.py`), each with its
latest live check, and the trusted domains. Live check: Exa fetches the rule's `source_url`, Gemini
answers whether the page still states the same months and conditions. Status is `verified`,
`mismatch` or `error`. Results are cached for 24 hours (errors are not cached).

**Input**: none.

### Example

Also returns `sources_used`: every page Exa used recently (`url`, `title`, `domain`, `date`, `step`, `used_at`).
Only public page info is stored, never the user's facts or queries.

Response:
```json
{
  "rules": [
    {
      "id": "work-based-three-months",
      "description": "If employment ends early, a work-based permit held for 2 years or less has a 3-month protection period to find a new job.",
      "months": 3,
      "applies_to": [
        "work_based with no more than 2 years on a work-based permit"
      ],
      "applies_when": [
        {
          "permit_type": "work_based",
          "years_on_work_permit": {
            "operator": "lte",
            "value": 2
          }
        }
      ],
      "source_url": "https://migri.fi/en/-/changes-to-work-based-residence-permits-protection-period-for-unemployment-and-new-notification-obligation-for-employers?languageId=en_US",
      "in_force_since": "2025-06-11",
      "last_verified": "2026-11-14",
      "live_check": {
        "rule_id": "work-based-three-months",
        "status": "verified",
        "checked_at": "2026-11-14T09:00:00+00:00",
        "evidence_snippet": "Example check result: the page states the same months and conditions."
      }
    },
    {
      "id": "specialist-or-long-term-work-six-months",
      "description": "If employment ends early, a specialist or EU Blue Card holder, or a work-based permit holder with over 2 years in Finland, has a 6-month protection period to find a new job.",
      "months": 6,
      "applies_to": [
        "specialist_blue_card",
        "work_based with over 2 years on a work-based permit"
      ],
      "applies_when": [
        {
          "permit_type": "specialist_blue_card"
        },
        {
          "permit_type": "work_based",
          "years_on_work_permit": {
            "operator": "gt",
            "value": 2
          }
        }
      ],
      "source_url": "https://migri.fi/en/-/changes-to-work-based-residence-permits-protection-period-for-unemployment-and-new-notification-obligation-for-employers?languageId=en_US",
      "in_force_since": "2025-06-11",
      "last_verified": "2026-11-14",
      "live_check": {
        "rule_id": "specialist-or-long-term-work-six-months",
        "status": "verified",
        "checked_at": "2026-11-14T09:00:00+00:00",
        "evidence_snippet": "Example check result: the page states the same months and conditions."
      }
    },
    {
      "id": "not-tied-to-employment",
      "description": "The employment-based protection period does not apply to student, family-based, permanent, or EU/EEA citizen permit types.",
      "months": null,
      "applies_to": [
        "student",
        "family_based",
        "permanent",
        "eu_eea_citizen"
      ],
      "applies_when": [
        {
          "permit_type": "student"
        },
        {
          "permit_type": "family_based"
        },
        {
          "permit_type": "permanent"
        },
        {
          "permit_type": "eu_eea_citizen"
        }
      ],
      "source_url": "https://migri.fi/en/-/changes-to-work-based-residence-permits-protection-period-for-unemployment-and-new-notification-obligation-for-employers?languageId=en_US",
      "in_force_since": "2025-06-11",
      "last_verified": "2026-11-14",
      "live_check": {
        "rule_id": "not-tied-to-employment",
        "status": "verified",
        "checked_at": "2026-11-14T09:00:00+00:00",
        "evidence_snippet": "Example check result: the page states the same months and conditions."
      }
    }
  ],
  "trusted_domains": [
    "migri.fi",
    "kela.fi",
    "infofinland.fi",
    "tyomarkkinatori.fi"
  ]
}
```

---

## POST /chat

The guided chat behind the web app. There are no accounts and nothing is stored on the server: the
browser keeps the session and sends it with each request.

Facts are merged in this order (later wins): the current `facts`, facts Gemini reads from the latest
user message, tapped `answers`, then `edited_facts` (what the user corrected on the card always wins).
Gemini only reads the latest message when it's from the user, so old messages aren't re-read.

Steps: `about_you` → `deadline` → `this_week`. The chat stays on `about_you` and
asks one question at a time until the deadline has what it needs. After that, send `action: "next"`
(the quick reply) to move on. If an edit makes a needed fact unknown, it goes back to `about_you`.

**Input**

| Field | Notes |
| --- | --- |
| `messages` | `[{role: "user" or "assistant", text}]` |
| `facts` | The current "What we know so far" card |
| `answers` | Tapped answers, keyed by question `id` |
| `edited_facts` | Fields the user corrected on the card |
| `step` | The step the browser is on |
| `action` | `"next"` to move to the next step |

**Output**

| Field | Notes |
| --- | --- |
| `reply` | Short, calm, plain-language message |
| `step` | Current step |
| `facts` | Updated "What we know so far" card |
| `confirmed_fields` | Fields the user tapped or edited in this request (the rest are guesses from their message) |
| `question` | The next question (`about_you` only), same shape as in `/intake` |
| `quick_replies` | e.g. `{"value": "next", "label": "Show me this week"}` |
| `deadline` | From step `deadline` on, same as in `/plan` |
| `plan` | From step `this_week` on, the `/plan` response |
| `out_of_scope`, `link` | If the job was outside Finland |

### Example

Request:
```json
{
  "messages": [
    {
      "role": "user",
      "text": "I'm from India and worked in a restaurant in Helsinki for a year on a work permit. My job ended on 1 November."
    }
  ],
  "facts": {},
  "answers": {},
  "edited_facts": {},
  "step": null,
  "action": null
}
```

Response:
```json
{
  "reply": "Thank you. Here is your deadline and the rule behind it. Take your time with it.",
  "step": "deadline",
  "facts": {
    "citizenship_group": "other",
    "citizenship_country": "India",
    "permit_type": "work_based",
    "years_on_work_permit": 1.0,
    "job_end_date": "2026-11-01",
    "city": "Helsinki",
    "field": "restaurant worker",
    "studied_in_finland": false,
    "family_in_finland": false
  },
  "confirmed_fields": [],
  "quick_replies": [
    {
      "value": "next",
      "label": "Show me this week"
    }
  ],
  "deadline": {
    "status": "ok",
    "explanation": "If employment ends early, a work-based permit held for 2 years or less has a 3-month protection period to find a new job. Based on your last day of work, the date is 2027-02-01.",
    "applies": true,
    "months": 3,
    "deadline_date": "2027-02-01",
    "days_left": 79,
    "possible_dates": [],
    "missing": [],
    "rule_id": "work-based-three-months",
    "source": {
      "title": "Migri – Changes to work-based residence permits",
      "url": "https://migri.fi/en/-/changes-to-work-based-residence-permits-protection-period-for-unemployment-and-new-notification-obligation-for-employers?languageId=en_US"
    },
    "verified": true,
    "check_status": "verified",
    "live_checks": [
      {
        "rule_id": "work-based-three-months",
        "status": "verified",
        "checked_at": "2026-11-14T09:00:00+00:00",
        "evidence_snippet": "Example check result: the page states a 3-month period for permits held 2 years or less."
      }
    ]
  },
  "out_of_scope": false,
  "mock": true
}
```

---

## POST /chat/stream

Same input and final result as `/chat`, sent as server-sent events so the roadmap can fill in live.
Each event is a line `data: {json}`:

| Event | Meaning |
| --- | --- |
| `{"type": "progress", "stage": ...}` | `reading_situation`, `checking_rules`, `finding_steps` |
| `{"type": "exa", "status": "searching", "purpose", "query", "domains", "category"}` | Exa started a search (e.g. purpose `unemployment benefits` on `kela.fi`) |
| `{"type": "exa", "status": "found", "purpose", "query", "results": [{title, url, published}], "count"}` | What that search found |
| `{"type": "exa", "status": "cached", "purpose", "count"}` | Reused a search from the last 24 hours |
| `{"type": "partial", "key": "deadline" / "plan", "data": ...}` | A piece of the result is ready |
| `{"type": "result", "data": <ChatResponse>}` | The final `/chat` response |
| `{"type": "error"}` | Something failed; the browser falls back to `/chat` |

---

## POST /steps/update (and /steps/update/stream)

The app shows the plan as one numbered list, just "Step 1, Step 2, …" with no week labels: the plan's 3 first
actions (`this_week`), then its later steps (`timeline`, skipping "Week 1", which repeats them), then the Plan B
options. The date from the rules engine is shown once above the list, as "You can stay in Finland to look for work
until …" (the word "deadline" is not shown to users). Each step has "Add info about this step".

**Input**: `{"facts": {...}, "plan": <PlanResponse>, "step": 2, "note": "I already registered last week"}`
(`step` is 1-based in the order above; `note` max 500 characters).

1. Plain keyword rules (no AI) pick up new facts from the note, only low-risk ones: `unemployment_fund`,
   `registered_jobseeker`, `studied_in_finland`, `family_in_finland`, `city`. Facts behind the date (permit,
   years, last day) are only changed in "What we know so far", so a phrase like "last week" can't move the date.
2. The usual Exa searches run (cached 24h; they follow the updated facts) plus one extra search on the note.
3. One Gemini call rewrites the plan with the note. Code keeps steps before `step` exactly as they were and takes
   `step` onward from the new plan.

**Output**: `plan` (merged), `facts`, `facts_update`, `updated_from`, `mock`, `message`. Without Gemini or Exa (or
with `USE_MOCK=true`) the steps stay as they were, the new facts are still saved, and `message` says so. The stream
sends the usual Exa/Gemini activity events, then `{"type": "result", "data": ...}`.

---

## POST /ask

Ask anything about your situation. Exa's Answer endpoint answers with citations. Questions about rules
(permits, benefits, registering) are limited to the trusted official domains, by system prompt and by keeping
only citations from those domains; if none remain, it says so instead of guessing. Off-topic questions get a
polite no without calling Exa. Answers are cached for 24 hours.

**Input**: `{"question": "...", "facts": {...}}` (facts add context: permit, city, field).

**Output**: `answer`, `sources` (`title`, `url`, `domain`, `date`), `suggested_roadmap_step` (`week1`,
`week2`, `week4`, `week8`, `final` or `deadline`, when the answer fits a step), `off_topic`, `official_only`,
`facts_update` (new facts found in the question that differ from the current situation, e.g. `{"years_on_work_permit": 3}`;
the app sends them to `/chat` as `edited_facts` so the roadmap rebuilds), `mock`. A question that is only a
correction ("I've actually been here 3 years") updates the situation without calling Exa.

### Example

Request:
```json
{"question": "Can I get unemployment benefit from Kela?", "facts": {"permit_type": "work_based", "city": "Helsinki"}}
```

Response (illustrative):
```json
{
  "answer": "If you live in Finland and are registered as an unemployed jobseeker, you may get labour market subsidy from Kela...",
  "sources": [{"title": "Kela – Unemployment", "url": "https://www.kela.fi/unemployment", "domain": "kela.fi", "date": null}],
  "suggested_roadmap_step": "week1",
  "off_topic": false,
  "official_only": true,
  "mock": false
}
```

---

## POST /opportunities (and /opportunities/stream)

Separate from the roadmap (which stays short: deadline and this week's 3 steps). Returns only **Perks and
support**: 3 Exa searches (one per perk) on the trusted domains plus the city's official sites (`CITY_DOMAINS`
in the country config), and 1 Gemini call to sort them, run in parallel and cached for 24 hours. Every item has
an Exa source URL and the page date Exa reported (`source_date`, `null` if the page has none); nothing is
invented. Without Exa it comes back empty with `mock: true`.

| Field | What it is | Rules enforced in code |
| --- | --- | --- |
| `perks_and_support.certificate` | How to get the job search certificate (proof you're a jobseeker), shown first: `name`, `how_to_get`, `source_url`, `source_date` | Only from the certificate search |
| `perks_and_support.discounts` | City discounts for unemployed jobseekers: `name`, `discount`, `proof_needed`, `city`, `source_url`, `source_date` | Only discounts Exa found, max 6 |
| `perks_and_support.incentives` | Employer hiring incentives: `name`, `what_it_is`, `conditions_plain`, `may_apply`, `caveat`, `source_url`, `source_date` | Never claims eligibility ("may apply"); conditions like "3 months unemployed" that clash with the permit deadline get a plain caveat |
| `counts` | `certificate`, `discounts`, `incentives`, `total` | |

**Context.dev** (optional, `CONTEXT_DEV_API_KEY`): before Gemini runs, the top page Exa found for each perk is read in
full with `POST /v1/web/scrape` (`formats.json` with a schema per perk, `mainContentOnly`), up to 3 pages per city,
cached 24h. Certificate steps and discounts then come straight from the page; incentive pages are given to Gemini as
the page's full details so it can judge "may apply". Those items have `read_by: "context.dev"`. If Context.dev is
not set up or fails, everything comes from Exa + Gemini as before.

The stream sends the same events as `/chat/stream`, with the partial `perks_and_support`.
Example: `backend/mocks/opportunities.json` (used for `USE_MOCK=true`).
