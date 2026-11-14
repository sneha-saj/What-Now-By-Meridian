"""Which Plan B permits fit this person. Plain code; sources come from Exa, wording from Gemini."""

from __future__ import annotations

from models import Facts

NO_PERMIT_RISK = ("Your right to stay in Finland doesn't depend on this job, so you don't need a backup permit. "
                  "Focus on income and your job search.")
NONE_FIT = ("We couldn't find another permit that clearly fits your situation. "
            "Check with Migri or your union before your deadline.")


def candidates(f: Facts, permit: str | None) -> list[dict]:
    """[{id, option, who_it_fits, query}] for the permits that could fit, most relevant first."""
    if permit in {"eu_eea_citizen", "permanent", "student", "family_based"}:
        return []
    out = [{
        "id": "new_employer",
        "option": "A new work-based residence permit",
        "who_it_fits": "Anyone who gets a job offer from a new employer before the deadline.",
        "query": "apply for a new work-based residence permit with a new employer Finland",
    }]
    if f.studied_in_finland:
        out.append({
            "id": "job_seeker_graduate",
            "option": "Residence permit to look for work after graduating",
            "who_it_fits": "People who completed a degree or research in Finland.",
            "query": "residence permit for looking for work after graduation Finland",
        })
    if f.family_in_finland:
        out.append({
            "id": "family",
            "option": "Family-based residence permit",
            "who_it_fits": "People whose spouse, partner or other close family member lives in Finland.",
            "query": "family-based residence permit Finland spouse",
        })
    out.append({
        "id": "entrepreneur",
        "option": "Residence permit for an entrepreneur",
        "who_it_fits": "People who want to start or run their own business in Finland.",
        "query": "residence permit for an entrepreneur Finland",
    })
    return out
