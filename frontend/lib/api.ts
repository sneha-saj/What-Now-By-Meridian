export type Facts = {
  lost_job?: boolean | null;
  citizenship_group?: "eu_eea" | "other" | "unknown" | null;
  citizenship_country?: string | null;
  permit_type?: string | null;
  years_on_work_permit?: number | "under_2" | "over_2" | "not_sure" | null;
  job_end_date?: string | null;
  job_end_date_approximate?: boolean | null;
  city?: string | null;
  field?: string | null;
  studied_in_finland?: boolean | null;
  family_in_finland?: boolean | null;
};

export type Source = { title: string; url: string; highlight?: string | null; published?: string | null };
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
  rule_in_force_since?: string | null;
  deadline_is_approximate?: boolean;
  source: Source;
  verified: boolean;
  check_status: "verified" | "mismatch" | "error" | "none";
  live_checks: LiveCheck[];
  warning?: string | null;
  warning_link?: string | null;
};
export type LiveCheck = { status: "verified" | "mismatch" | "error"; checked_at: string; evidence_snippet: string };
export type Rule = { id: string; description: string; months: number | null; applies_to: string[]; source_url: string; in_force_since: string; last_verified: string; live_check: LiveCheck };
export type UsedSource = { url: string; title: string; domain: string; date?: string | null; step: string; used_at: string };
export type RulesResponse = { rules: Rule[]; trusted_domains: string[]; sources_used?: UsedSource[] };
export type RoadStep = "week1" | "wayin" | "week2" | "week4" | "week8" | "final" | "deadline";
export type AskSource = { title: string; url: string; domain: string; date?: string | null };
export type AskResponse = {
  answer: string;
  sources: AskSource[];
  suggested_roadmap_step?: RoadStep;
  off_topic: boolean;
  official_only: boolean;
  mock: boolean;
};
export type PrimaryAction = { kind: "open_link" | "reach_out" | "copy_draft" | "check_conditions"; label: string; url?: string | null };
/** Short display fields on every roadmap and opportunity item (long fields stay for the expanded view). */
export type Short = { title_short: string; why_short: string; primary_action?: PrimaryAction | null };
export type Action = Short & { title: string; why: string; how: string[]; sources: Source[] };
export type TimelineStep = Short & { week: string; steps: string[]; sources: Source[] };
export type PlanBOption = Short & {
  id: string;
  option: string;
  who_it_fits: string;
  why: string;
  latest_start_date?: string | null;
  sources: Source[];
};
export type PlanResponse = {
  deadline: Deadline;
  this_week: Action[];
  timeline: TimelineStep[];
  plan_b: PlanBOption[];
  plan_b_note?: string | null;
  disclaimer: string;
  mock: boolean;
};

export type Company = {
  name: string;
  why_relevant: string;
  url: string;
  hiring_now: boolean;
  hiring_evidence?: string | null;
  hiring_evidence_date?: string | null;
  source: Source;
};
export type Contact = { name: string; role: string; company: string; why_this_person: string; profile_url: string };
export type Community = {
  name: string;
  type: "professional_group" | "event" | "union";
  date_if_event?: string | null;
  url: string;
  published?: string | null;
};
export type Draft = { to: string; profile_url: string; message: string };
export type ReferralResponse = {
  companies: Company[];
  contacts: Contact[];
  communities: Community[];
  drafts: Draft[];
  mock: boolean;
};

export type Step = "about_you" | "deadline" | "this_week" | "find_your_way_in";
export const STEPS: { id: Step; label: string }[] = [
  { id: "about_you", label: "About you" },
  { id: "deadline", label: "Your deadline" },
  { id: "this_week", label: "This week" },
  { id: "find_your_way_in", label: "Find your way in" },
];
export type ChatMessage = { role: "user" | "assistant"; text: string };
export type ChatRequest = {
  messages: ChatMessage[];
  facts: Facts;
  answers?: Partial<Facts>;
  edited_facts?: Partial<Facts>;
  step?: Step | null;
  action?: "next" | null;
};
export type ChatResponse = {
  reply: string;
  step: Step;
  facts: Facts;
  confirmed_fields: (keyof Facts)[];
  question?: Question;
  quick_replies: Option[];
  deadline?: Deadline;
  plan?: PlanResponse;
  referrals?: ReferralResponse;
  out_of_scope: boolean;
  link?: string;
  links?: Source[];
  mock: boolean;
};

export type ProgressStage = "reading_situation" | "checking_rules" | "finding_steps" | "finding_people";
export type ExaEvent = {
  type: "exa";
  status: "searching" | "found" | "cached";
  purpose: string;
  query?: string;
  domains?: string[];
  category?: string | null;
  results?: { title: string; url: string; published?: string | null }[];
  count?: number;
};
export type GeminiEvent = { type: "gemini"; status: "working" | "done" | "cached"; purpose: string };
export type AppEvent = { type: "app"; who: "gemini" | "code" | "app"; text: string };
export type StreamEvent =
  | { type: "progress"; stage: ProgressStage }
  | ExaEvent
  | GeminiEvent
  | AppEvent
  | { type: "partial"; key: "deadline"; data: Deadline }
  | { type: "partial"; key: "plan"; data: PlanResponse }
  | { type: "partial"; key: "referrals"; data: ReferralResponse }
  | { type: "partial"; key: "hidden_jobs" | "people" | "support" | "events" | "perks_and_support"; data: unknown };

async function streamPost<T>(path: string, body: unknown, onEvent: (e: StreamEvent) => void): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) throw new Error(`stream failed (${res.status})`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      if (!part.startsWith("data: ")) continue;
      const event = JSON.parse(part.slice(6));
      if (event.type === "result") return event.data as T;
      if (event.type === "error") throw new Error(`${path} failed`);
      onEvent(event as StreamEvent);
    }
  }
  throw new Error("stream ended without a result");
}

/** POST /chat/stream: live events, then the result. Falls back to /chat. */
export async function chatStream(req: ChatRequest, onEvent: (e: StreamEvent) => void): Promise<ChatResponse> {
  try {
    return await streamPost<ChatResponse>("/chat/stream", req, onEvent);
  } catch {
    return api.chat(req);
  }
}

/** POST /opportunities/stream: live events and sections, then the result. Falls back to /opportunities. */
export async function opportunitiesStream(facts: Facts, onEvent: (e: StreamEvent) => void): Promise<OpportunitiesResponse> {
  try {
    return await streamPost<OpportunitiesResponse>("/opportunities/stream", { facts }, onEvent);
  } catch {
    return post<OpportunitiesResponse>("/opportunities", { facts });
  }
}

export type HiddenJob = Short & { company: string; signal: string; signal_date: string; source_url: string; why_it_fits: string; action: "reach_out" };
export type OppContact = Short & { name: string; role: string; company: string; why_this_person: string; profile_url: string; draft: string };
export type SupportItem = Short & { name: string; what_it_is: string; why_it_may_apply: string; eligibility_note: string; source_url: string; source_date?: string | null };
export type EventItem = Short & { name: string; date: string; place?: string | null; url: string; why_relevant: string };
export type Certificate = Short & { name: string; how_to_get: string; source_url: string; source_date?: string | null };
export type Discount = Short & { name: string; discount: string; proof_needed: string; city: string; source_url: string; source_date?: string | null };
export type Incentive = Short & { name: string; what_it_is: string; conditions_plain: string; may_apply: boolean; caveat: string; source_url: string; source_date?: string | null };
export type PerksAndSupport = { certificate?: Certificate | null; discounts: Discount[]; incentives: Incentive[] };
export type OpportunitiesResponse = {
  hidden_jobs: HiddenJob[];
  people: OppContact[];
  support: SupportItem[];
  events: EventItem[];
  perks_and_support: PerksAndSupport;
  counts?: { hidden_jobs: number; people: number; support: number; events: number; certificate: number; discounts: number; incentives: number; total: number };
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
  chat: (req: ChatRequest) => post<ChatResponse>("/chat", req),
  ask: (question: string, facts: Facts) => post<AskResponse>("/ask", { question, facts }),
  rules: async () => {
    const res = await fetch("/api/rules");
    if (!res.ok) throw new Error(`/rules failed (${res.status})`);
    return res.json() as Promise<RulesResponse>;
  },
};
