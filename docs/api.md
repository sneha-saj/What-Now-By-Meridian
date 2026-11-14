# What Now? API

Backend: FastAPI in `backend/`. Run `make dev`, then open the interactive docs at
http://localhost:8000/docs (every endpoint has the examples below built in).

**Example persona** used throughout: a restaurant worker from India on a work-based permit, 1 year in
Finland, living in Helsinki, whose job ended on 1 November 2026.

The example responses are saved in `backend/mocks/` and are what the API returns when `USE_MOCK=true`.
Official sources in them are real pages. Companies and people are clearly marked samples
(`example.com`), because we don't put invented businesses or people in front of users as real.

Every response has `mock: true` when a fallback was used (no API key, or a call failed). The demo always runs.

| Endpoint | Purpose |
| --- | --- |
| `POST /intake` | Turn the user's sentence into facts; ask up to 3 questions the deadline still needs |
| `POST /plan` | Deadline, 3 actions for this week, a timeline and plan B, all with official sources |
| `GET /rules` | The deadline rules, their latest live check against Migri, and trusted domains |
| `POST /referrals` | Companies hiring, people to contact, communities, and draft messages |
| `POST /chat` | Guided chat: the same steps, one message at a time, with a live "Your situation" card |
| `POST /chat/stream` | Same as `/chat`, streamed with live progress, Exa activity and partial results |
| `POST /opportunities` (+ `/stream`) | Hidden jobs, people, support, events and perks, all from live Exa sources |
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

Questions are deterministic: the Finland config (`backend/countries/finland.py`) lists `REQUIRED_FIELDS`
(citizenship group, permit type, years on a work permit, job end date), then `OPTIONAL_FIELDS` (city, field), with a
fixed `QUESTION_BANK`. Gemini only extracts facts; code picks the next missing field. Optional questions have
"Skip" (stored as `""`, not asked again). Approximate date answers arrive as `about:YYYY-MM-DD` and set
`job_end_date_approximate`; the deadline then has `deadline_is_approximate: true`.

Facts: `citizenship_group` (`eu_eea` / `other` / `unknown`), `citizenship_country`, `permit_type`,
`years_on_work_permit` (number, or `under_2` / `over_2` / `not_sure`), `job_end_date`, `city`, `field`,
`studied_in_finland`, `family_in_finland`.

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

## POST /referrals

1. **Companies**: Exa company search, up to 8, hiring in the user's field or labour-shortage sectors, in or near their city.
2. **People**: Exa people search at the top 3 companies, 2 each: public professional profiles only.
3. **Communities**: international professional groups, events in the next 30 days, union career services.
4. **Drafts**: Gemini writes one short, polite message per contact (max 80 words) mentioning one real
   detail from the sources. Drafts only: nothing is ever sent.

At most 7 Exa searches per request (run in parallel), cached for 24 hours, to control credits. Without Exa, only real
help services are listed (no invented companies or people).

**Input**: `{"facts": {...}}`. Uses `city`, `field` and the other facts.

**Output**: `companies` (`name`, `why_relevant` (one sentence, max 20 words), `url`, `hiring_now`, `hiring_evidence` (a job post or careers page, when found), `source`; companies with hiring evidence come first), `contacts` (`name`, `role`,
`company`, `why_this_person`, `profile_url`), `communities` (`name`, `type`, `date_if_event`, `url`),
`drafts` (`to`, `profile_url`, `message`).

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
  "companies": [
    {
      "name": "Example Bistro Oy (sample)",
      "why_relevant": "A Helsinki restaurant group hiring kitchen staff who speak English.",
      "url": "https://example.com/bistro",
      "source": {
        "title": "Example Bistro Oy (sample)",
        "url": "https://example.com/bistro"
      },
      "hiring_now": true,
      "hiring_evidence": "https://example.com/bistro/careers"
    },
    {
      "name": "Example Hotels Finland (sample)",
      "why_relevant": "Hotels are a labour-shortage sector and hire restaurant workers.",
      "url": "https://example.com/hotels",
      "source": {
        "title": "Example Hotels Finland (sample)",
        "url": "https://example.com/hotels"
      },
      "hiring_now": false,
      "hiring_evidence": null
    }
  ],
  "contacts": [
    {
      "name": "Sample Contact",
      "role": "Head Chef",
      "company": "Example Bistro Oy (sample)",
      "why_this_person": "Leads the kitchen team that is hiring.",
      "profile_url": "https://example.com/profile/sample-contact"
    }
  ],
  "communities": [
    {
      "name": "International House Helsinki",
      "type": "professional_group",
      "date_if_event": null,
      "url": "https://www.ihhelsinki.fi/"
    },
    {
      "name": "Work in Finland",
      "type": "professional_group",
      "date_if_event": null,
      "url": "https://www.workinfinland.com/"
    }
  ],
  "drafts": [
    {
      "to": "Sample Contact",
      "profile_url": "https://example.com/profile/sample-contact",
      "message": "Hi, I saw that Example Bistro is hiring line cooks in Helsinki. I've worked in a Helsinki restaurant kitchen for a year and I'm looking for my next role. Would you have a few minutes for a short chat, or could you point me to the right person? Thank you! [Your name]"
    }
  ],
  "mock": true
}
```

---

## POST /chat

The guided chat behind the web app. There are no accounts and nothing is stored on the server: the
browser keeps the session and sends it with each request.

Facts are merged in this order (later wins): the current `facts`, facts Gemini reads from the latest
user message, tapped `answers`, then `edited_facts` (what the user corrected on the card always wins).
Gemini only reads the latest message when it's from the user, so old messages aren't re-read.

Steps: `about_you` → `deadline` → `this_week` → `find_your_way_in`. The chat stays on `about_you` and
asks one question at a time until the deadline has what it needs. After that, send `action: "next"`
(the quick reply) to move on. If an edit makes a needed fact unknown, it goes back to `about_you`.

**Input**

| Field | Notes |
| --- | --- |
| `messages` | `[{role: "user" or "assistant", text}]` |
| `facts` | The current "Your situation" card |
| `answers` | Tapped answers, keyed by question `id` |
| `edited_facts` | Fields the user corrected on the card |
| `step` | The step the browser is on |
| `action` | `"next"` to move to the next step |

**Output**

| Field | Notes |
| --- | --- |
| `reply` | Short, calm, plain-language message |
| `step` | Current step |
| `facts` | Updated "Your situation" card |
| `confirmed_fields` | Fields the user tapped or edited in this request (the rest are guesses from their message) |
| `question` | The next question (`about_you` only), same shape as in `/intake` |
| `quick_replies` | e.g. `{"value": "next", "label": "Show me this week"}` |
| `deadline` | From step `deadline` on, same as in `/plan` |
| `plan` | From step `this_week` on, the `/plan` response |
| `referrals` | On step `find_your_way_in`, the `/referrals` response |
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
| `{"type": "progress", "stage": ...}` | `reading_situation`, `checking_rules`, `finding_steps`, `finding_people` |
| `{"type": "exa", "status": "searching", "purpose", "query", "domains", "category"}` | Exa started a search (e.g. purpose `unemployment benefits` on `kela.fi`) |
| `{"type": "exa", "status": "found", "purpose", "query", "results": [{title, url, published}], "count"}` | What that search found |
| `{"type": "exa", "status": "cached", "purpose", "count"}` | Reused a search from the last 24 hours |
| `{"type": "partial", "key": "deadline" / "plan" / "referrals", "data": ...}` | A piece of the result is ready |
| `{"type": "result", "data": <ChatResponse>}` | The final `/chat` response |
| `{"type": "error"}` | Something failed; the browser falls back to `/chat` |

---

## POST /ask

Ask anything about your situation. Exa's Answer endpoint answers with citations. Questions about rules
(permits, benefits, registering) are limited to the trusted official domains, by system prompt and by keeping
only citations from those domains; if none remain, it says so instead of guessing. Off-topic questions get a
polite no without calling Exa. Answers are cached for 24 hours.

**Input**: `{"question": "...", "facts": {...}}` (facts add context: permit, city, field).

**Output**: `answer`, `sources` (`title`, `url`, `domain`, `date`), `suggested_roadmap_step` (`week1`, `wayin`,
`week2`, `week4`, `week8`, `final` or `deadline`, when the answer fits a step), `off_topic`, `official_only`, `mock`.

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

Separate from the roadmap (which stays short: deadline and this week's 3 steps). About 11 Exa searches and
2 Gemini calls per city and field, run in parallel and cached for 24 hours. Every item has an Exa source URL;
nothing is invented. Without Exa the sections come back empty with `mock: true`.

| Section | What it is | Rules enforced in code |
| --- | --- | --- |
| `hidden_jobs` | Companies with hiring signals (new openings, expansions, funding, new locations) in the user's city and field: `company`, `signal`, `signal_date`, `source_url`, `why_it_fits`, `action: "reach_out"` | Signal page dated within the last 60 days |
| `people` | Public professional contacts at the top 2 companies: `name`, `role`, `company`, `why_this_person`, `profile_url`, `draft` | Draft max 80 words (template otherwise); may mention an employer incentive that may apply |
| `support` | Support types from the country config (labour market training, language courses, mentoring, start-up grant): `name`, `what_it_is`, `why_it_may_apply`, `eligibility_note`, `source_url`, `source_date` | Only plausible matches; always "May apply, check the conditions." |
| `events` | Recruitment fairs, meetups and community events: `name`, `date`, `place`, `url`, `why_relevant` | Stated date within the next 30 days |
| `perks_and_support` | `certificate` (how to get the job search certificate, first), `discounts` (`name`, `discount`, `proof_needed`, `city`, `source_url`, `source_date`), `incentives` (`name`, `what_it_is`, `conditions_plain`, `may_apply`, `caveat`, `source_url`, `source_date`) | Only discounts Exa found; incentive conditions like "3 months unemployed" that clash with the permit deadline get a plain caveat |

Searches use the trusted domains plus the city's official sites (`CITY_DOMAINS` in the country config).
The stream sends the same events as `/chat/stream`, with partial sections `hidden_jobs`, `support`, `events`,
`perks_and_support` and `people`. Example: `backend/mocks/opportunities.json` (used for `USE_MOCK=true`).
