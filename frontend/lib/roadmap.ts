import { isSample } from "./format";
import type { Deadline, ExaEvent, PlanResponse, ReferralResponse, RoadStep, Source, TimelineStep } from "./api";

export type NodeId = "today" | RoadStep;
export type NodeState = "searching" | "found" | "done";

/** The one live, specific thing Exa found for a step (name/date/link): what judges should notice. */
export type LiveFind = { label: string; url: string; date?: string | null; note?: string };

export type RoadNode = {
  id: NodeId;
  label: string;
  startsOn?: Date;
  title: string;
  state: NodeState;
  live: boolean; // has a live find from Exa (otherwise "saved guide")
  liveFind?: LiveFind;
  searchingText?: string;
  source?: Source;
};

export type RoadmapInput = {
  today: Date;
  ready: boolean;
  deadline?: Deadline;
  plan?: PlanResponse;
  referrals?: ReferralResponse;
  searching: Searching;
  doneActions: Record<number, boolean>;
  doneNodes: Partial<Record<NodeId, boolean>>;
};

/** Which roadmap node each kind of Exa search feeds. */
const PURPOSE_NODE: Record<string, NodeId> = {
  "rule check": "deadline",
  "registering as a jobseeker": "week1",
  "unemployment benefits": "week1",
  "official guidance": "week1",
  "labour-shortage sectors": "week4",
  "other permits": "final",
  companies: "wayin",
  "job posts": "wayin",
  people: "wayin",
  events: "wayin",
  unions: "wayin",
};

const PURPOSE_TEXT: Record<string, string> = {
  "rule check": "Reading migri.fi",
  companies: "Searching the web for companies hiring",
  "job posts": "Looking for current job posts",
  people: "Looking for people at those companies",
  events: "Looking for events in the next 30 days",
  unions: "Looking for union career services",
};

/** Searches still running, per node, with the text to show. */
export type Searching = Partial<Record<NodeId, { pending: number; text: string }>>;

export function applyExaEvent(s: Searching, e: ExaEvent): Searching {
  const node = PURPOSE_NODE[e.purpose];
  if (!node) return s;
  const cur = s[node] ?? { pending: 0, text: "" };
  if (e.status === "searching") {
    const where = e.domains?.length ? e.domains.join(", ") : null;
    const text = PURPOSE_TEXT[e.purpose] ?? (where ? `Searching ${where}` : `Searching the web for ${e.purpose}`);
    return { ...s, [node]: { pending: cur.pending + 1, text } };
  }
  return { ...s, [node]: { ...cur, pending: Math.max(0, cur.pending - 1) } };
}

export function timelineFor(plan: PlanResponse | undefined, label: string): TimelineStep | undefined {
  return plan?.timeline.find((t) => t.week.toLowerCase() === label.toLowerCase());
}

const asFind = (s?: Source, note?: string): LiveFind | undefined =>
  s ? { label: s.title, url: s.url, date: s.published, note } : undefined;

/** The live, specific item for each step, only when it really came from Exa (not the saved guide). */
export function liveFindFor(id: NodeId, i: RoadmapInput): LiveFind | undefined {
  const planLive = !!i.plan && !i.plan.mock;
  const refs = i.referrals;
  if (id === "deadline")
    return i.deadline?.check_status === "verified"
      ? { label: "Migri: protection period after your job ends", url: i.deadline.source.url, note: "Checked against migri.fi today" }
      : undefined;
  if (id === "wayin" && refs) {
    if (refs.companies.some((x) => isSample(x.url))) return undefined; // saved example, not live
    const c = refs.companies.find((x) => x.hiring_evidence);
    if (c) return { label: `${c.name}: job post`, url: c.hiring_evidence!, date: c.hiring_evidence_date, note: "Hiring now" };
    const e = refs.communities.find((g) => g.date_if_event);
    if (e) return { label: e.name, url: e.url, date: e.date_if_event, note: "Event" };
    if (refs.companies[0]) return asFind(refs.companies[0].source);
    return undefined;
  }
  if (!planLive) return undefined;
  if (id === "week1") return asFind(i.plan!.this_week[0]?.sources[0]);
  if (id === "final") return asFind(i.plan!.plan_b[0]?.sources[0]);
  const label = { week2: "Week 2", week4: "Week 4", week8: "Week 8" }[id as "week2" | "week4" | "week8"];
  return label ? asFind(timelineFor(i.plan, label)?.sources[0]) : undefined;
}

const DAY = 86_400_000;
const WEEKS: { id: NodeId; week: number; label: string }[] = [
  { id: "week1", week: 1, label: "Week 1" },
  { id: "wayin", week: 1, label: "Week 1" },
  { id: "week2", week: 2, label: "Week 2" },
  { id: "week4", week: 4, label: "Week 4" },
  { id: "week8", week: 8, label: "Week 8" },
  { id: "final", week: 0, label: "Final weeks" },
];

export function buildNodes(i: RoadmapInput): RoadNode[] {
  const { today, ready, deadline, plan, referrals, searching, doneActions, doneNodes } = i;
  if (!ready) return [];
  const end = deadline?.deadline_date ? new Date(deadline.deadline_date + "T00:00:00") : null;
  const nodes: RoadNode[] = [{ id: "today", label: "Today", startsOn: today, title: "Where you are now", state: "found", live: false }];

  for (const w of WEEKS) {
    const startsOn = w.week ? new Date(today.getTime() + (w.week - 1) * 7 * DAY) : end ? new Date(end.getTime() - 14 * DAY) : undefined;
    if (end && startsOn && w.week > 1 && startsOn > end) continue; // after the deadline
    const busy = (searching[w.id]?.pending ?? 0) > 0;
    let has = false;
    let title: string = w.label;
    let source: Source | undefined;
    if (w.id === "week1") {
      has = !!plan?.this_week.length;
      title = "3 things to do this week";
      source = plan?.this_week[0]?.sources[0];
    } else if (w.id === "wayin") {
      has = !!referrals && (referrals.companies.length + referrals.contacts.length + referrals.communities.length > 0);
      title = "Find your way in";
      source = referrals?.companies[0]?.source;
    } else if (w.id === "final") {
      const t = timelineFor(plan, "Final weeks");
      has = !!t || !!plan?.plan_b.length || !!plan?.plan_b_note;
      title = plan?.plan_b.length ? "Your Plan B, if no job comes in time" : t?.steps[0] ?? "Final weeks";
      source = plan?.plan_b[0]?.sources[0] ?? t?.sources[0];
    } else {
      const t = timelineFor(plan, w.label);
      has = !!t;
      title = t?.steps[0] ?? w.label;
      source = t?.sources[0];
    }
    if (!has && !busy) continue;
    const find = has ? liveFindFor(w.id, i) : undefined;
    const allDone = w.id === "week1" ? !!plan && plan.this_week.every((_, k) => doneActions[k]) : !!doneNodes[w.id];
    nodes.push({
      id: w.id, label: w.label, startsOn, title,
      state: busy && !has ? "searching" : allDone ? "done" : "found",
      live: !!find, liveFind: find, searchingText: searching[w.id]?.text, source,
    });
  }

  const deadlineBusy = (searching.deadline?.pending ?? 0) > 0;
  if (deadline || deadlineBusy) {
    const find = liveFindFor("deadline", i);
    nodes.push({
      id: "deadline", label: "Your deadline", startsOn: end ?? undefined,
      title: deadline?.deadline_date ? "Your deadline" : "Your permit",
      state: deadline ? "found" : "searching",
      live: !!find, liveFind: find,
      searchingText: searching.deadline?.text ?? "Reading migri.fi",
      source: deadline?.source,
    });
  }
  return nodes;
}

/** True when every step after "Today" has a live find. */
export function allLive(nodes: RoadNode[]) {
  const steps = nodes.filter((n) => n.id !== "today");
  return steps.length > 0 && steps.every((n) => n.live);
}

export function firstSentence(text?: string | null, max = 220): string | null {
  if (!text) return null;
  const clean = text.replace(/\s+/g, " ").replace(/^\W+/, "").trim();
  const first = clean.split(/(?<=[.!?])\s/)[0] ?? clean;
  return first.length > max ? first.slice(0, max).replace(/\s\S*$/, "") + "…" : first;
}
