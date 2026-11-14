from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

from rules import Citizenship, DeadlineInput, PermitType


class Facts(BaseModel):
    citizenship: Optional[Citizenship] = None
    permit_type: Optional[PermitType] = None
    job_end_date: Optional[date] = None
    over_two_years_on_work_permit: Optional[bool] = None
    occupation: Optional[str] = None
    city: Optional[str] = None

    def to_rules(self) -> DeadlineInput:
        return DeadlineInput(
            citizenship=self.citizenship,
            permit_type=self.permit_type,
            job_end_date=self.job_end_date,
            over_two_years_on_work_permit=self.over_two_years_on_work_permit,
        )


class Source(BaseModel):
    title: str
    url: str
    snippet: Optional[str] = None


class Option(BaseModel):
    label: str
    value: str | bool


class Question(BaseModel):
    field: str
    question: str
    kind: Literal["choice", "date"] = "choice"
    options: list[Option] = Field(default_factory=list)


class IntakeRequest(BaseModel):
    text: str


class IntakeResponse(BaseModel):
    facts: Facts
    questions: list[Question]
    mock: bool


class PlanRequest(BaseModel):
    facts: Facts


class Deadline(BaseModel):
    status: str
    reason: str
    deadline: Optional[date] = None
    months: Optional[int] = None
    days_left: Optional[int] = None
    missing: list[str] = Field(default_factory=list)
    source: Source


class Step(BaseModel):
    title: str
    detail: str
    sources: list[Source]


class PlanResponse(BaseModel):
    deadline: Deadline
    this_week: list[Step]
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
