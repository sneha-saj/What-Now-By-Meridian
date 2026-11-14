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
