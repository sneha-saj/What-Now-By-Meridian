export type Facts = {
  citizenship_group?: "eu_eea" | "other" | "unknown" | null;
  citizenship_country?: string | null;
  permit_type?: string | null;
  years_on_work_permit?: number | "under_2" | "over_2" | "not_sure" | null;
  job_end_date?: string | null;
  city?: string | null;
  field?: string | null;
  studied_in_finland?: boolean | null;
  family_in_finland?: boolean | null;
};

export type Source = { title: string; url: string; highlight?: string | null };
export type Option = { value: string; label: string };
export type Question = { id: keyof Facts; question: string; kind: "choice" | "date"; options: Option[] };

export type IntakeResponse = {
  facts?: Facts;
  missing_questions: Question[];
  out_of_scope: boolean;
  message?: string;
  link?: string;
  mock: boolean;
};

export type PossibleDate = { months: number; deadline_date?: string | null; rule_id: string };
export type Deadline = {
  status: "ok" | "not_applicable" | "needs_info" | "unclear";
  explanation: string;
  applies?: boolean | null;
  months?: number | null;
  deadline_date?: string | null;
  days_left?: number | null;
  possible_dates: PossibleDate[];
  missing: string[];
  rule_id?: string | null;
  source: Source;
  verified: boolean;
  live_checks: LiveCheck[];
  warning?: string | null;
  warning_link?: string | null;
};
export type LiveCheck = { status: "verified" | "mismatch" | "error"; checked_at: string; evidence_snippet: string };
export type Rule = { id: string; description: string; months: number | null; applies_to: string[]; source_url: string; in_force_since: string; last_verified: string; live_check: LiveCheck };
export type RulesResponse = { rules: Rule[]; trusted_domains: string[] };
export type Action = { title: string; why: string; how: string[]; sources: Source[] };
export type TimelineStep = { week: string; steps: string[]; sources: Source[] };
export type PlanBOption = { option: string; why: string; latest_start_date?: string | null; sources: Source[] };
export type PlanResponse = {
  deadline: Deadline;
  this_week: Action[];
  timeline: TimelineStep[];
  plan_b: PlanBOption[];
  disclaimer: string;
  mock: boolean;
};

export type Company = { name: string; why_relevant: string; url: string; source: Source };
export type Contact = { name: string; role: string; company: string; why_this_person: string; profile_url: string };
export type Community = { name: string; type: "professional_group" | "event" | "union"; date_if_event?: string | null; url: string };
export type Draft = { to: string; profile_url: string; message: string };
export type ReferralResponse = {
  companies: Company[];
  contacts: Contact[];
  communities: Community[];
  drafts: Draft[];
  mock: boolean;
};

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} failed (${res.status})`);
  return res.json();
}

export const api = {
  intake: (text: string, answers: Partial<Facts> = {}) => post<IntakeResponse>("/intake", { text, answers }),
  plan: (facts: Facts) => post<PlanResponse>("/plan", { facts }),
  referrals: (facts: Facts) => post<ReferralResponse>("/referrals", { facts }),
  rules: async () => {
    const res = await fetch("/api/rules");
    if (!res.ok) throw new Error(`/rules failed (${res.status})`);
    return res.json() as Promise<RulesResponse>;
  },
};
