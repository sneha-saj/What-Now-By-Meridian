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
  unemployment_fund?: "yes" | "no" | "not_sure" | null;
  registered_jobseeker?: "yes" | "no" | null;
  /** Personal questions Gemini picked for this person, asked before the steps. */
  to_ask?: string[] | null;
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
export type LiveCheck = { status: "verified" | "mismatch" | "error"; checked_at: string; evidence_snippet: string; read_by?: "context.dev" | "exa" | null };
export type Rule = { id: string; description: string; months: number | null; applies_to: string[]; source_url: string; in_force_since: string; last_verified: string; live_check: LiveCheck };
export type UsedSource = { url: string; title: string; domain: string; date?: string | null; step: string; used_at: string };
export type RulesResponse = { rules: Rule[]; trusted_domains: string[]; sources_used?: UsedSource[] };
export type RoadStep = "week1" | "week2" | "week4" | "week8" | "final" | "deadline";
export type AskSource = { title: string; url: string; domain: string; date?: string | null };
export type AskResponse = {
  answer: string;
  sources: AskSource[];
  suggested_roadmap_step?: RoadStep;
  off_topic: boolean;
  official_only: boolean;
  facts_update?: Partial<Facts>;
  mock: boolean;
};
export type PrimaryAction = { kind: "open_link" | "check_conditions"; label: string; url?: string | null };
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

export type Step = "about_you" | "deadline" | "this_week";
export const STEPS: { id: Step; label: string }[] = [
  { id: "about_you", label: "About you" },
  { id: "deadline", label: "Your deadline" },
  { id: "this_week", label: "This week" },
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
  out_of_scope: boolean;
  link?: string;
  links?: Source[];
  mock: boolean;
  /** True when the saved sample person is shown (demo mode), not this person's situation. */
  demo?: boolean;
};

export type ProgressStage = "reading_situation" | "checking_rules" | "finding_steps";
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
export type ContextEvent = { type: "context"; status: "reading" | "read" | "cached" | "failed"; purpose: string; url: string; partial?: boolean };
export type StreamEvent =
  | { type: "progress"; stage: ProgressStage }
  | ContextEvent
  | ExaEvent
  | GeminiEvent
  | AppEvent
  | { type: "partial"; key: "deadline"; data: Deadline }
  | { type: "partial"; key: "plan"; data: PlanResponse }
  | { type: "partial"; key: "perks_and_support"; data: unknown };

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

export type StepsUpdateRequest = { facts: Facts; plan: PlanResponse; step: number; note: string };
export type StepsUpdateResponse = {
  plan: PlanResponse;
  facts: Facts;
  facts_update: Partial<Facts>;
  updated_from: number;
  mock: boolean;
  message?: string;
};

/** POST /steps/update/stream: add info to one step; it and the steps after it are rewritten (live Exa events first). */
export async function stepsUpdateStream(req: StepsUpdateRequest, onEvent: (e: StreamEvent) => void): Promise<StepsUpdateResponse> {
  try {
    return await streamPost<StepsUpdateResponse>("/steps/update/stream", req, onEvent);
  } catch {
    return post<StepsUpdateResponse>("/steps/update", req);
  }
}

/** POST /opportunities/stream: live events, then Perks and support. Falls back to /opportunities. */
export async function opportunitiesStream(facts: Facts, onEvent: (e: StreamEvent) => void): Promise<OpportunitiesResponse> {
  try {
    return await streamPost<OpportunitiesResponse>("/opportunities/stream", { facts }, onEvent);
  } catch {
    return post<OpportunitiesResponse>("/opportunities", { facts });
  }
}

export type Certificate = Short & { name: string; how_to_get: string; source_url: string; source_date?: string | null; read_by?: "context.dev" | null };
export type Discount = Short & { name: string; discount: string; proof_needed: string; city: string; source_url: string; source_date?: string | null; read_by?: "context.dev" | null };
export type Incentive = Short & { name: string; what_it_is: string; conditions_plain: string; may_apply: boolean; caveat: string; source_url: string; source_date?: string | null; read_by?: "context.dev" | null };
export type SupportItem = Short & {
  topic: string; name: string; what_it_is: string; how_to_get?: string | null; who_can_get_it?: string | null;
  source_url: string; source_date?: string | null; read_by?: "context.dev" | null;
};
/** A topic on Perks and support: picked by plain rules from the person's answers, with the reason. */
export type PerkTopic = { id: string; title: string; label: string; reason: string };
export type PerksAndSupport = {
  topics?: PerkTopic[]; certificate?: Certificate | null; discounts: Discount[]; incentives: Incentive[]; support?: SupportItem[];
};
export type OpportunitiesResponse = {
  perks_and_support: PerksAndSupport;
  counts?: { certificate: number; discounts: number; incentives: number; support?: number; total: number };
  mock: boolean;
  demo?: boolean;
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
  chat: (req: ChatRequest) => post<ChatResponse>("/chat", req),
  ask: (question: string, facts: Facts) => post<AskResponse>("/ask", { question, facts }),
  rules: async () => {
    const res = await fetch("/api/rules");
    if (!res.ok) throw new Error(`/rules failed (${res.status})`);
    return res.json() as Promise<RulesResponse>;
  },
};
