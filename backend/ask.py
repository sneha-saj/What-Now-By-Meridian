"""Plain-code helpers for /ask: is it on topic, is it about rules, which roadmap step does it belong to."""

from __future__ import annotations

import re

ON_TOPIC = re.compile(
    r"\b(job|jobs|work|working|employ\w*|unemploy\w*|laid off|layoff|fired|dismiss\w*|notice|contract|salary|pay|"
    r"permit|visa|residence|migri|kela|te[- ]?(office|services)|benefit\w*|allowance|subsidy|fund|union|"
    r"register\w*|jobseeker|cv|resume|interview|apply|application|employer|recruit\w*|career|hiring|refer\w*|"
    r"tax|vero|insurance|healthcare|housing|rent|deadline|months?|extend|renew|stay|leave finland|"
    r"study|student|degree|family|spouse|entrepreneur|business|finnish|language|course|training|finland)\b",
    re.I,
)
RULES = re.compile(
    r"\b(permit|visa|residence|migri|deadline|stay|extend|renew|protection period|kela|benefit\w*|allowance|"
    r"subsidy|unemploy\w*|register\w*|jobseeker|te[- ]?(office|services)|tax|insurance|entrepreneur permit|"
    r"family|spouse|student)\b",
    re.I,
)
STEPS = [
    ("deadline", r"\b(deadline|how long|stay|protection period|months?)\b"),
    ("final", r"\b(another permit|other permit|new permit|entrepreneur|family|spouse|student permit|plan b|leave)\b"),
    ("week1", r"\b(register\w*|jobseeker|kela|benefit\w*|allowance|subsidy|unemployment fund|te[- ]?(office|services))\b"),
    ("wayin", r"\b(compan\w+|hiring|refer\w*|network\w*|recruit\w*|contact|meetup|event|linkedin)\b"),
    ("week2", r"\b(cv|resume|interview|apply|application|job search)\b"),
    ("week4", r"\b(shortage|sector|retrain\w*|course|training|language)\b"),
]

OFF_TOPIC_REPLY = ("I can only help with questions about losing a job in Finland: your permit, benefits, "
                   "job search and the people who can help. Try asking about one of those.")


def on_topic(q: str) -> bool:
    return bool(ON_TOPIC.search(q))


def about_rules(q: str) -> bool:
    return bool(RULES.search(q))


def suggested_step(q: str) -> str | None:
    return next((step for step, pat in STEPS if re.search(pat, q, re.I)), None)
