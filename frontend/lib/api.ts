export type Facts = {
  citizenship?: "finnish" | "eu" | "non_eu" | null;
  permit_type?: string | null;
  job_end_date?: string | null;
  over_two_years_on_work_permit?: boolean | null;
  occupation?: string | null;
  city?: string | null;
};

export type Source = { title: string; url: string; snippet?: string | null };
export type Option = { label: string; value: string | boolean };
export type Question = { field: keyof Facts; question: string; kind: "choice" | "date"; options: Option[] };

export type IntakeResponse = { facts: Facts; questions: Question[]; mock: boolean };

export type Deadline = {
  status: "ok" | "not_applicable" | "needs_info" | "unsupported";
  reason: string;
  deadline?: string | null;
  months?: number | null;
  days_left?: number | null;
  missing: string[];
  source: Source;
};
export type Step = { title: string; detail: string; sources: Source[] };
export type PlanResponse = { deadline: Deadline; this_week: Step[]; mock: boolean };

export type Referral = {
  name: string;
  role: string;
  organization: string;
  why: string;
  message: string;
  source: Source;
};
export type ReferralResponse = { referrals: Referral[]; mock: boolean };

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
  intake: (text: string) => post<IntakeResponse>("/intake", { text }),
  plan: (facts: Facts) => post<PlanResponse>("/plan", { facts }),
  referrals: (facts: Facts) => post<ReferralResponse>("/referrals", { facts }),
};
