import type { ExaEvent, RoadStep } from "./api";

/** Where an Exa search belongs: a step group, or the "how long you can stay" header ("deadline"). */
export type NodeId = "today" | RoadStep;

/** Which roadmap node each kind of Exa search feeds. */
const PURPOSE_NODE: Record<string, NodeId> = {
  "rule check": "deadline",
  "registering as a jobseeker": "week1",
  "unemployment benefits": "week1",
  "official guidance": "week1",
  "labour-shortage sectors": "week4",
  "other permits": "final",
};

const PURPOSE_TEXT: Record<string, string> = {
  "rule check": "Reading migri.fi",
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

export function firstSentence(text?: string | null, max = 220): string | null {
  if (!text) return null;
  const clean = text.replace(/\s+/g, " ").replace(/^\W+/, "").trim();
  const first = clean.split(/(?<=[.!?])\s/)[0] ?? clean;
  return first.length > max ? first.slice(0, max).replace(/\s\S*$/, "") + "…" : first;
}
