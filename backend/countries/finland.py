"""Finland-specific sources, intake choices, and deadline rules."""

TRUSTED_DOMAINS = ["migri.fi", "kela.fi", "infofinland.fi", "tyomarkkinatori.fi"]

PERMIT_TYPES = [
    {"id": "work-based", "label": "Work-based"},
    {"id": "specialist-eu-blue-card", "label": "Specialist / EU Blue Card"},
    {"id": "student", "label": "Student"},
    {"id": "family-based", "label": "Family-based"},
    {"id": "permanent", "label": "Permanent"},
    {"id": "eu-eea-citizen", "label": "EU/EEA citizen"},
    {"id": "not-sure", "label": "Not sure"},
]

SOURCE_URL = "https://migri.fi/en/end-of-employment"
SOURCE_TITLE = "Migri – End of employment"
IN_FORCE_SINCE = "2025-06-11"

DEADLINE_RULES = [
    {
        "id": "work-based-three-months",
        "description": "Most work-based permit holders have 3 months to find a new job after employment ends early.",
        "months": 3,
        "applies_to": ["work-based permit held for less than 2 years"],
        "source_url": SOURCE_URL,
        "in_force_since": IN_FORCE_SINCE,
        "last_verified": "2026-11-14",
    },
    {
        "id": "specialist-or-long-term-work-six-months",
        "description": "Specialists, EU Blue Card holders, and people with more than 2 years on a work-based permit have 6 months.",
        "months": 6,
        "applies_to": ["specialist", "EU Blue Card", "work-based permit held for more than 2 years"],
        "source_url": SOURCE_URL,
        "in_force_since": IN_FORCE_SINCE,
        "last_verified": "2026-11-14",
    },
    {
        "id": "not-tied-to-employment",
        "description": "This employment-based deadline does not apply to permanent residents, students, family-based permit holders, or EU/EEA/Finnish citizens.",
        "months": None,
        "applies_to": ["permanent", "student", "family-based", "EU/EEA citizen", "Finnish citizen"],
        "source_url": SOURCE_URL,
        "in_force_since": IN_FORCE_SINCE,
        "last_verified": "2026-11-14",
    },
]
