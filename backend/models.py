from datetime import date
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

CitizenshipGroup = Literal["eu_eea", "other", "unknown"]
YearsBucket = Literal["under_2", "over_2", "not_sure"]


class Facts(BaseModel):
    citizenship_group: Optional[CitizenshipGroup] = None
    citizenship_country: Optional[str] = None
    permit_type: Optional[str] = None
    # A number of years, or a bucket from the tap-to-answer question.
    years_on_work_permit: Optional[Union[float, YearsBucket]] = None
    job_end_date: Optional[date] = None
    city: Optional[str] = None
    field: Optional[str] = None
    studied_in_finland: Optional[bool] = None
    family_in_finland: Optional[bool] = None

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


class Source(BaseModel):
    title: str
    url: str
    highlight: Optional[str] = None


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
    source: Source
    verified: bool = False
    live_checks: list[dict] = Field(default_factory=list)
    warning: Optional[str] = None
    warning_link: Optional[str] = None


class Action(BaseModel):
    title: str
    why: str
    how: list[str]
    sources: list[Source]


class TimelineStep(BaseModel):
    week: str
    steps: list[str]
    sources: list[Source]


class PlanBOption(BaseModel):
    option: str
    why: str
    latest_start_date: Optional[str] = None
    sources: list[Source]


class PlanResponse(BaseModel):
    deadline: Deadline
    this_week: list[Action]
    timeline: list[TimelineStep]
    plan_b: list[PlanBOption]
    disclaimer: str
    mock: bool


class ReferralRequest(BaseModel):
    facts: Facts


class Referral(BaseModel):
    name: str
    role: str
    organization: str
    why: str
    message: str
    source: Source


class ReferralResponse(BaseModel):
    referrals: list[Referral]
    mock: bool
