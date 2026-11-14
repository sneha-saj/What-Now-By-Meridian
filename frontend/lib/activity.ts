import type { StreamEvent } from "./api";
import { hostOf } from "@/components/primitives";

export type Who = "gemini" | "exa" | "code";
export type LogLine = { id: number; who: Who; text: string; at: string };

const PURPOSE_LABEL: Record<string, string> = {
  "rule check": "Migri's rule page",
  perks: "perks and support for jobseekers",
};

let seq = 0;
const now = () => new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

/** Turn a live stream event into one short, plain line for the "What's happening" log (or null). */
export function toLogLine(e: StreamEvent): LogLine | null {
  const line = (who: Who, text: string): LogLine => ({ id: ++seq, who, text, at: now() });
  if (e.type === "app") return line(e.who === "gemini" ? "gemini" : "code", e.text.charAt(0).toLowerCase() + e.text.slice(1));
  if (e.type === "gemini") {
    if (e.status === "working") return line("gemini", `is ${e.purpose}…`);
    if (e.status === "cached") return line("gemini", `reused today's answer (${e.purpose})`);
    return null;
  }
  if (e.type === "exa") {
    const what = PURPOSE_LABEL[e.purpose] ?? e.purpose;
    if (e.status === "searching") {
      const where = e.domains?.length ? ` on ${e.domains.join(", ")}` : " on the web";
      return line("exa", `is searching${where} for ${what}…`);
    }
    if (e.status === "found") {
      const hosts = Array.from(new Set((e.results ?? []).map((r) => hostOf(r.url)))).slice(0, 3);
      return line("exa", `found ${e.count ?? 0} ${e.count === 1 ? "page" : "pages"} for ${what}${hosts.length ? `: ${hosts.join(", ")}` : ""}`);
    }
    return line("exa", `reused today's search for ${what} (${e.count ?? 0} results)`);
  }
  return null;
}
