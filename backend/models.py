from datetime import date
from typing import Literal, Optional, Union

from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator

CitizenshipGroup = Literal["eu_eea", "other", "unknown"]
YearsBucket = Literal["under_2", "over_2", "not_sure"]


class Facts(BaseModel):
    lost_job: Optional[bool] = None  # did they lose (or are about to lose) a job? None = not clear yet
    citizenship_group: Optional[CitizenshipGroup] = None
    citizenship_country: Optional[str] = None
    permit_type: Optional[str] = None
    # A number of years, or a bucket from the tap-to-answer question.
    years_on_work_permit: Optional[Union[float, YearsBucket]] = None
    job_end_date: Optional[date] = None
    job_end_date_approximate: Optional[bool] = None  # from a vague answer like "about a week ago"
    city: Optional[str] = None
    field: Optional[str] = None
    studied_in_finland: Optional[bool] = None
    family_in_finland: Optional[bool] = None
    unemployment_fund: Optional[Literal["yes", "no", "not_sure"]] = None  # earnings-related allowance vs Kela
    registered_jobseeker: Optional[Literal["yes", "no"]] = None
    # Personal questions Gemini picked for this person (ids from PERSONAL_QUESTIONS), asked before the steps.
    to_ask: Optional[list[str]] = None

    def years(self) -> Optional[float]:
        """Years as a number for the rules engine; buckets map to a value on the right side of 2."""
        y = self.years_on_work_permit
        if isinstance(y, (int, float)):
            return float(y)
        return {"under_2": 1.0, "over_2": 3.0}.get(y or "")


class Option(BaseModel):
    value: str
    label: str


class Question(BaseModel):
    id: str
    question: str
    kind: Literal["choice", "date"] = "choice"
    options: list[Option] = Field(default_factory=list)


class IntakeRequest(BaseModel):
    text: str = ""
    answers: dict = Field(default_factory=dict)


class IntakeResponse(BaseModel):
    facts: Optional[Facts] = None
    missing_questions: list[Question] = Field(default_factory=list)
    out_of_scope: bool = False
    message: Optional[str] = None
    link: Optional[str] = None
    mock: bool = False


class PlanRequest(BaseModel):
    facts: Facts


# ---------- Short display fields ----------
# Every roadmap and opportunity item carries title_short (max 6 words), why_short (max 12 words) and one
# primary_action for the compact view. Longer fields (steps, highlights, eligibility) stay for the expanded view.
# If Gemini didn't provide short versions (or overshot), they're derived from the long fields here, in code.

TITLE_WORDS, WHY_WORDS = 6, 12


def shorten(text: str | None, max_words: int) -> str:
    words = " ".join((text or "").split()).split(" ")
    if len(words) <= max_words:
        return " ".join(words).strip()
    return " ".join(words[:max_words]).rstrip(",;:–-") + "…"


def _domain(url: str | None) -> str:
    host = urlparse(url or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


class PrimaryAction(BaseModel):
    kind: Literal["open_link", "check_conditions"]
    label: str
    url: Optional[str] = None


class Display(BaseModel):
    title_short: str = ""
    why_short: str = ""
    primary_action: Optional[PrimaryAction] = None

    def _defaults(self) -> tuple[str, str, Optional[PrimaryAction]]:  # overridden per item type
        return "", "", None

    @model_validator(mode="after")
    def _fill_short_fields(self):
        title, why, action = self._defaults()
        self.title_short = shorten(self.title_short or title, TITLE_WORDS)
        self.why_short = shorten(self.why_short or why, WHY_WORDS)
        if self.primary_action is None:
            self.primary_action = action
        return self


class Source(BaseModel):
    title: str
    url: str
    highlight: Optional[str] = None
    published: Optional[str] = None  # page date reported by Exa, when known


class PossibleDate(BaseModel):
    months: int
    deadline_date: Optional[date] = None
    rule_id: str


class Deadline(BaseModel):
    status: Literal["ok", "not_applicable", "needs_info", "unclear"]
    explanation: str
    applies: Optional[bool] = None
    months: Optional[int] = None
    deadline_date: Optional[date] = None
    days_left: Optional[int] = None
    possible_dates: list[PossibleDate] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    rule_id: Optional[str] = None
    rule_in_force_since: Optional[str] = None
    deadline_is_approximate: bool = False
    source: Source
    verified: bool = False
    check_status: Literal["verified", "mismatch", "error", "none"] = "none"
    live_checks: list[dict] = Field(default_factory=list)
    warning: Optional[str] = None
    warning_link: Optional[str] = None


class Action(Display):
    title: str
    why: str
    how: list[str]
    sources: list[Source]

    def _defaults(self):
        src = self.sources[0] if self.sources else None
        return self.title, self.why, PrimaryAction(kind="open_link", label=f"Go to {_domain(src.url)}", url=src.url) if src else None


class TimelineStep(Display):
    week: str
    steps: list[str]
    sources: list[Source]

    def _defaults(self):
        src = self.sources[0] if self.sources else None
        return (self.steps[0] if self.steps else self.week), self.week, (
            PrimaryAction(kind="open_link", label=f"Go to {_domain(src.url)}", url=src.url) if src else None)


class PlanBOption(Display):
    id: str = ""
    option: str
    who_it_fits: str = ""
    why: str
    latest_start_date: Optional[str] = None
    sources: list[Source]

    def _defaults(self):
        src = self.sources[0] if self.sources else None
        return self.option, self.who_it_fits or self.why, (
            PrimaryAction(kind="check_conditions", label="Check the conditions", url=src.url) if src else None)


class PlanResponse(BaseModel):
    deadline: Deadline
    this_week: list[Action]
    timeline: list[TimelineStep]
    plan_b: list[PlanBOption]
    plan_b_note: Optional[str] = None
    disclaimer: str
    mock: bool


class StepsUpdateRequest(BaseModel):
    facts: Facts
    plan: PlanResponse
    step: int = Field(ge=1)  # 1-based, in the order the steps are shown: this week's 3, later weeks, Plan B
    note: str = Field(min_length=1, max_length=500)


class StepsUpdateResponse(BaseModel):
    plan: PlanResponse
    facts: Facts
    facts_update: dict = Field(default_factory=dict)
    updated_from: int
    mock: bool = False
    message: Optional[str] = None


Step = Literal["about_you", "deadline", "this_week"]
STEPS: list[str] = ["about_you", "deadline", "this_week"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    facts: dict = Field(default_factory=dict)
    answers: dict = Field(default_factory=dict)
    edited_facts: dict = Field(default_factory=dict)
    step: Optional[Step] = None
    action: Optional[Literal["next"]] = None


class QuickReply(BaseModel):
    value: str
    label: str


class ChatResponse(BaseModel):
    reply: str
    step: Step
    facts: Facts
    confirmed_fields: list[str] = Field(default_factory=list)
    question: Optional[Question] = None
    quick_replies: list[QuickReply] = Field(default_factory=list)
    deadline: Optional[Deadline] = None
    plan: Optional[PlanResponse] = None
    out_of_scope: bool = False
    link: Optional[str] = None
    links: list[Source] = Field(default_factory=list)
    mock: bool = False


class AskRequest(BaseModel):
    question: str
    facts: Facts = Field(default_factory=Facts)


class AskSource(BaseModel):
    title: str
    url: str
    domain: str
    date: Optional[str] = None


class AskResponse(BaseModel):
    answer: str
    sources: list[AskSource] = Field(default_factory=list)
    suggested_roadmap_step: Optional[Literal["week1", "week2", "week4", "week8", "final", "deadline"]] = None
    off_topic: bool = False
    official_only: bool = False
    facts_update: dict = Field(default_factory=dict)  # new facts found in the question; the roadmap rebuilds
    mock: bool = False


# ---------- /opportunities ----------

class Certificate(Display):
    name: str
    how_to_get: str
    source_url: str
    source_date: Optional[str] = None

    def _defaults(self):
        return "Get your job search certificate", self.how_to_get, PrimaryAction(
            kind="open_link", label="How to get it", url=self.source_url)


class Discount(Display):
    name: str
    discount: str
    proof_needed: str
    city: str
    source_url: str
    source_date: Optional[str] = None

    def _defaults(self):
        return self.name, self.discount, PrimaryAction(kind="open_link", label="See the discount", url=self.source_url)


class Incentive(Display):
    name: str
    what_it_is: str
    conditions_plain: str
    may_apply: bool
    caveat: str
    source_url: str
    source_date: Optional[str] = None

    def _defaults(self):
        return self.name, self.caveat or self.what_it_is, PrimaryAction(
            kind="check_conditions", label="Check the conditions", url=self.source_url)


class PerksAndSupport(BaseModel):
    certificate: Optional[Certificate] = None
    discounts: list[Discount] = Field(default_factory=list)
    incentives: list[Incentive] = Field(default_factory=list)


class OpportunitiesRequest(BaseModel):
    facts: Facts


class OpportunityCounts(BaseModel):
    certificate: int = 0
    discounts: int = 0
    incentives: int = 0
    total: int = 0


class OpportunitiesResponse(BaseModel):
    perks_and_support: PerksAndSupport = Field(default_factory=PerksAndSupport)
    counts: OpportunityCounts = Field(default_factory=OpportunityCounts)
    mock: bool = False

    @model_validator(mode="after")
    def _count_sections(self):
        p = self.perks_and_support
        c = OpportunityCounts(certificate=int(p.certificate is not None), discounts=len(p.discounts),
                              incentives=len(p.incentives))
        c.total = c.certificate + c.discounts + c.incentives
        self.counts = c
        return self
