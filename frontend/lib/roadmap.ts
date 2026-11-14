import type { Deadline, ExaEvent, PlanResponse, ReferralResponse, Source, TimelineStep } from "./api";

export type NodeId = "today" | "week1" | "week2" | "week4" | "week8" | "final" | "deadline";
export type NodeState = "searching" | "found" | "done";

export type RoadNode = {
  id: NodeId;
  label: string;
  startsOn?: Date;
  title: string;
  state: NodeState;
  live: boolean; // data found live on the web by Exa (not sample data)
  searchingText?: string;
  source?: Source;
};

/** Which roadmap node each kind of Exa search feeds. */
const PURPOSE_NODE: Record<string, NodeId> = {
  "rule check": "deadline",
  "registering as a jobseeker": "week1",
  "unemployment benefits": "week1",
  "official guidance": "week1",
  "labour-shortage sectors": "week4",
  "other permits": "final",
  companies: "week2",
  "job posts": "week2",
  people: "week2",
  events: "week2",
  unions: "week2",
};

const PURPOSE_TEXT: Record<string, string> = {
  "rule check": "Reading migri.fi",
  companies: "Searching the web for companies hiring",
  "job posts": "Looking for current job posts",
  people: "Looking for people at those companies",
  events: "Looking for groups and events in the next 30 days",
  unions: "Looking for union career services",
};

/** Searches still running, per node, with the text to show. */
export type Searching = Partial<Record<NodeId, { pending: number; text: string }>>;

export function applyExaEvent(s: Searching, e: ExaEvent): Searching {
  const node = PURPOSE_NODE[e.purpose] ?? (e.purpose.startsWith("plan_b") ? "final" : undefined);
  if (!node) return s;
  const cur = s[node] ?? { pending: 0, text: "" };
  if (e.status === "searching") {
    const where = e.domains?.length ? e.domains.join(", ") : null;
    const text = PURPOSE_TEXT[e.purpose] ?? (where ? `Searching ${where}` : `Searching the web for ${e.purpose}`);
    return { ...s, [node]: { pending: cur.pending + 1, text } };
  }
  return { ...s, [node]: { ...cur, pending: Math.max(0, cur.pending - 1) } };
}

const DAY = 86_400_000;
const WEEK_NODES: { id: NodeId; week: number; label: string; timeline: string }[] = [
  { id: "week1", week: 1, label: "Week 1", timeline: "Week 1" },
  { id: "week2", week: 2, label: "Week 2", timeline: "Week 2" },
  { id: "week4", week: 4, label: "Week 4", timeline: "Week 4" },
  { id: "week8", week: 8, label: "Week 8", timeline: "Week 8" },
  { id: "final", week: 0, label: "Final weeks", timeline: "Final weeks" },
];

export function timelineFor(plan: PlanResponse | undefined, label: string): TimelineStep | undefined {
  return plan?.timeline.find((t) => t.week.toLowerCase() === label.toLowerCase());
}

export function buildNodes(args: {
  today: Date;
  ready: boolean; // facts complete
  deadline?: Deadline;
  plan?: PlanResponse;
  referrals?: ReferralResponse;
  searching: Searching;
  doneActions: Record<number, boolean>;
  doneNodes: Partial<Record<NodeId, boolean>>;
}): RoadNode[] {
  const { today, ready, deadline, plan, referrals, searching, doneActions, doneNodes } = args;
  if (!ready) return [];
  const end = deadline?.deadline_date ? new Date(deadline.deadline_date + "T00:00:00") : null;
  const planLive = !!plan && !plan.mock;
  const nodes: RoadNode[] = [{ id: "today", label: "Today", startsOn: today, title: "Where you are now", state: "found", live: false }];

  for (const w of WEEK_NODES) {
    const startsOn = w.week ? new Date(today.getTime() + (w.week - 1) * 7 * DAY) : end ? new Date(end.getTime() - 14 * DAY) : undefined;
    if (end && startsOn && w.week && startsOn > end) continue; // after the deadline
    const busy = (searching[w.id]?.pending ?? 0) > 0;
    const t = timelineFor(plan, w.timeline);
    let title = t?.steps[0];
    let source = t?.sources[0];
    let has = !!t;
    let live = planLive;
    if (w.id === "week1") {
      has = !!plan?.this_week.length;
      title = "3 things to do this week";
      source = plan?.this_week[0]?.sources[0];
    }
    if (w.id === "week2" && referrals && (referrals.companies.length || referrals.contacts.length || referrals.communities.length)) {
      has = true;
      title = title ?? "Reach out to people who can refer you";
      source = source ?? referrals.companies[0]?.source;
      live = live || !referrals.mock || referrals.companies.length > 0;
    }
    if (w.id === "final") {
      has = has || !!plan?.plan_b.length || !!plan?.plan_b_note;
      title = plan?.plan_b.length ? "Your Plan B, if no job comes in time" : title ?? "Final weeks";
      source = plan?.plan_b[0]?.sources[0] ?? source;
    }
    if (!has && !busy) continue;
    const allDone = w.id === "week1" ? !!plan && plan.this_week.every((_, i) => doneActions[i]) : !!doneNodes[w.id];
    nodes.push({
      id: w.id, label: w.label, startsOn, title: title ?? w.label,
      state: busy && !has ? "searching" : allDone ? "done" : "found",
      live, searchingText: searching[w.id]?.text, source,
    });
  }

  const deadlineBusy = (searching.deadline?.pending ?? 0) > 0;
  if (deadline || deadlineBusy) {
    nodes.push({
      id: "deadline", label: "Your deadline", startsOn: end ?? undefined,
      title: deadline?.deadline_date ? "Your deadline" : "Your permit",
      state: deadline ? "found" : "searching",
      live: deadline?.check_status === "verified",
      searchingText: searching.deadline?.text ?? "Reading migri.fi",
      source: deadline?.source,
    });
  }
  return nodes;
}

export function firstSentence(text?: string | null, max = 220): string | null {
  if (!text) return null;
  const clean = text.replace(/\s+/g, " ").replace(/^\W+/, "").trim();
  const first = clean.split(/(?<=[.!?])\s/)[0] ?? clean;
  return first.length > max ? first.slice(0, max).replace(/\s\S*$/, "") + "…" : first;
}
