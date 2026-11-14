"""Finland-specific permit choices, trusted sources, and deadline rules."""

TRUSTED_DOMAINS = ["migri.fi", "kela.fi", "infofinland.fi", "tyomarkkinatori.fi"]

PERMIT_TYPES = [
    {"id": "work_based", "label": "Work-based"},
    {"id": "specialist_blue_card", "label": "Specialist / EU Blue Card"},
    {"id": "student", "label": "Student"},
    {"id": "family_based", "label": "Family-based"},
    {"id": "permanent", "label": "Permanent"},
    {"id": "eu_eea_citizen", "label": "EU/EEA citizen"},
    {"id": "not_sure", "label": "Not sure"},
]

SOURCE_URL = (
    "https://migri.fi/en/-/changes-to-work-based-residence-permits-"
    "protection-period-for-unemployment-and-new-notification-obligation-for-employers"
    "?languageId=en_US"
)
SOURCE_TITLE = "Migri – Changes to work-based residence permits"
IN_FORCE_SINCE = "2025-06-11"
LAST_VERIFIED = "2026-11-14"

# `applies_when` is intentionally declarative so rules.py contains no Finnish
# permit policy or deadline values.
DEADLINE_RULES = [
    {
        "id": "work-based-three-months",
        "description": "If employment ends early, a work-based permit held for 2 years or less has a 3-month protection period to find a new job.",
        "months": 3,
        "applies_to": ["work_based with no more than 2 years on a work-based permit"],
        "applies_when": [
            {"permit_type": "work_based", "years_on_work_permit": {"operator": "lte", "value": 2}}
        ],
        "source_url": SOURCE_URL,
        "in_force_since": IN_FORCE_SINCE,
        "last_verified": LAST_VERIFIED,
    },
    {
        "id": "specialist-or-long-term-work-six-months",
        "description": "If employment ends early, a specialist or EU Blue Card holder, or a work-based permit holder with over 2 years in Finland, has a 6-month protection period to find a new job.",
        "months": 6,
        "applies_to": ["specialist_blue_card", "work_based with over 2 years on a work-based permit"],
        "applies_when": [
            {"permit_type": "specialist_blue_card"},
            {"permit_type": "work_based", "years_on_work_permit": {"operator": "gt", "value": 2}},
        ],
        "source_url": SOURCE_URL,
        "in_force_since": IN_FORCE_SINCE,
        "last_verified": LAST_VERIFIED,
    },
    {
        "id": "not-tied-to-employment",
        "description": "The employment-based protection period does not apply to student, family-based, permanent, or EU/EEA citizen permit types.",
        "months": None,
        "applies_to": ["student", "family_based", "permanent", "eu_eea_citizen"],
        "applies_when": [
            {"permit_type": "student"},
            {"permit_type": "family_based"},
            {"permit_type": "permanent"},
            {"permit_type": "eu_eea_citizen"},
        ],
        "source_url": SOURCE_URL,
        "in_force_since": IN_FORCE_SINCE,
        "last_verified": LAST_VERIFIED,
    },
]


# ---------- Intake questions ----------
# Code (not AI) picks the next missing field in this order and asks its fixed question.
# Required fields are what the deadline needs. Optional ones personalise the search; "Skip" stores "".
REQUIRED_FIELDS = ["citizenship_group", "permit_type", "years_on_work_permit", "job_end_date"]
OPTIONAL_FIELDS = ["city", "field"]

QUESTION_BANK = {
    # Asked first, only when the message didn't say anything about losing a job.
    "lost_job": {
        "question": "Have you lost your job, or are you about to?",
        "options": [
            {"value": "true", "label": "Yes"},
            {"value": "false", "label": "No, it's something else"},
        ],
    },
    "citizenship_group": {
        "question": "Are you a citizen of an EU or EEA country?",
        "options": [
            {"value": "eu_eea", "label": "Yes, EU / EEA"},
            {"value": "other", "label": "No, another country"},
            {"value": "unknown", "label": "Not sure"},
        ],
    },
    "permit_type": {
        "question": "What kind of residence permit do you have?",
        "options": [{"value": p["id"], "label": p["label"]} for p in PERMIT_TYPES if p["id"] != "eu_eea_citizen"],
    },
    "years_on_work_permit": {
        "question": "How long have you had a work-based permit in Finland, in total?",
        "options": [
            {"value": "under_2", "label": "2 years or less"},
            {"value": "over_2", "label": "More than 2 years"},
            {"value": "not_sure", "label": "Not sure"},
        ],
    },
    "job_end_date": {
        "question": "When was (or is) your last day of work?",
        "kind": "date",
        "options": "relative_dates",  # Today / About a week ago / About a month ago, computed from today
    },
    "city": {
        "question": "Which city do you live in?",
        "options": [
            {"value": "Helsinki", "label": "Helsinki"},
            {"value": "Espoo", "label": "Espoo"},
            {"value": "Vantaa", "label": "Vantaa"},
            {"value": "Tampere", "label": "Tampere"},
            {"value": "Turku", "label": "Turku"},
            {"value": "Oulu", "label": "Oulu"},
            {"value": "", "label": "Skip"},
        ],
    },
    "field": {
        "question": "What kind of work do you do?",
        "options": [
            {"value": "restaurant worker", "label": "Restaurant / hospitality"},
            {"value": "software developer", "label": "IT / software"},
            {"value": "nurse", "label": "Health and care"},
            {"value": "construction worker", "label": "Construction"},
            {"value": "warehouse worker", "label": "Logistics / warehouse"},
            {"value": "cleaner", "label": "Cleaning"},
            {"value": "", "label": "Skip"},
        ],
    },
}


# ---------- Opportunities ----------
# Official city sites searched alongside the trusted domains for local support, perks and incentives.
CITY_DOMAINS = {
    "helsinki": ["hel.fi", "myhelsinki.fi"],
    "espoo": ["espoo.fi"],
    "vantaa": ["vantaa.fi"],
    "tampere": ["tampere.fi"],
    "turku": ["turku.fi"],
    "oulu": ["ouka.fi"],
}

# Support types we look for. Each is one Exa search on trusted + city domains. Gemini then keeps only items
# whose eligibility text plausibly matches the user; we never claim eligibility.
SUPPORT_TYPES = [
    {"id": "labour_market_training", "name": "Labour market training",
     "query": "labour market training for unemployed jobseekers free courses"},
    {"id": "language_courses", "name": "Finnish or Swedish language courses",
     "query": "free Finnish language courses for unemployed immigrants"},
    {"id": "mentoring", "name": "Mentoring for internationals",
     "query": "mentoring programme for international jobseekers"},
    {"id": "startup_grant", "name": "Start-up grant",
     "query": "start-up grant for unemployed person starting a business"},
]

# Perks: always try the job search certificate first, then discounts and employer hiring incentives.
PERK_QUERIES = {
    "certificate": "how to get a job search certificate proof of unemployed jobseeker status for discounts",
    "discounts": "discounts for unemployed jobseekers swimming sports museums culture adult education courses",
    "incentives": "employer hiring subsidy for hiring an unemployed jobseeker city employment benefit",
}
