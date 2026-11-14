"""Oxylabs — fetch a company's career page (optional tech challenge).

Not wired in yet. Plan: after a hiring search finds a company, fetch its careers page via
Oxylabs Web Scraper API and extract open roles matching the user's occupation.
Enabled with ENABLE_OXYLABS=true plus OXYLABS_USERNAME / OXYLABS_PASSWORD.
"""

import os

import config

OXYLABS_ENDPOINT = "https://realtime.oxylabs.io/v1/queries"


def is_enabled() -> bool:
    return config.ENABLE_OXYLABS and bool(os.getenv("OXYLABS_USERNAME") and os.getenv("OXYLABS_PASSWORD"))


def fetch_career_page(url: str) -> str:
    """Return the rendered HTML of a careers page.

    TODO: POST {"source": "universal", "url": url, "render": "html"} to OXYLABS_ENDPOINT
    with basic auth (OXYLABS_USERNAME, OXYLABS_PASSWORD) and return results[0]["content"].
    """
    if not is_enabled():
        raise RuntimeError("Oxylabs is disabled (set ENABLE_OXYLABS=true and credentials).")
    raise NotImplementedError("Oxylabs career page fetch not implemented yet.")
