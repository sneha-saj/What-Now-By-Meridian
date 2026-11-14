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
  source: Source;
  verified: boolean;
  check_status: "verified" | "mismatch" | "error" | "none";
  live_checks: LiveCheck[];
  warning?: string | null;
  warning_link?: string | null;
};
export type LiveCheck = { status: "verified" | "mismatch" | "error"; checked_at: string; evidence_snippet: string };
export type Rule = { id: string; description: string; months: number | null; applies_to: string[]; source_url: string; in_force_since: string; last_verified: string; live_check: LiveCheck };
export type RulesResponse = { rules: Rule[]; trusted_domains: string[] };
export type Action = { title: string; why: string; how: string[]; sources: Source[] };
export type TimelineStep = { week: string; steps: string[]; sources: Source[] };
export type PlanBOption = {
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
  source: Source;
};
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
export type StreamEvent =
  | { type: "progress"; stage: ProgressStage }
  | ExaEvent
  | { type: "partial"; key: "deadline"; data: Deadline }
  | { type: "partial"; key: "plan"; data: PlanResponse }
  | { type: "partial"; key: "referrals"; data: ReferralResponse };

/** POST /chat/stream: calls onEvent for each live event, resolves with the result. Falls back to /chat. */
export async function chatStream(req: ChatRequest, onEvent: (e: StreamEvent) => void): Promise<ChatResponse> {
  try {
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
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
        if (event.type === "result") return event.data as ChatResponse;
        if (event.type === "error") throw new Error("chat failed");
        onEvent(event as StreamEvent);
      }
    }
    throw new Error("stream ended without a result");
  } catch {
    return api.chat(req);
  }
}

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
  rules: async () => {
    const res = await fetch("/api/rules");
    if (!res.ok) throw new Error(`/rules failed (${res.status})`);
    return res.json() as Promise<RulesResponse>;
  },
};
