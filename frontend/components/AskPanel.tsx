"use client";

import { useState } from "react";
import { api, type AskResponse, type Facts, type RoadStep } from "@/lib/api";
import { GlobeIcon } from "./icons";
import { Button, GentleWarning, SourceChip } from "./primitives";

export type AskEntry = { question: string; res: AskResponse; added?: boolean };

const STEP_NAME: Record<RoadStep, string> = {
  week1: "This week", week2: "Week 2", week4: "Week 4", week8: "Week 8",
  final: "Plan B", deadline: "Your deadline",
};

/** Ask tab: one input. Exa answers from live sources; answers can be pinned to a roadmap step. */
export function AskPanel({
  facts, entries, onEntry, onAdd,
}: { facts: Facts; entries: AskEntry[]; onEntry: (e: AskEntry) => void; onAdd: (i: number) => void }) {
  const [showAll, setShowAll] = useState(false);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  async function ask() {
    const question = q.trim();
    if (!question || busy) return;
    setBusy(true);
    setError(false);
    try {
      onEntry({ question, res: await api.ask(question, facts) });
      setQ("");
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="ask-title" className="space-y-4 rounded-3xl border border-rule bg-card p-5 shadow-[0_6px_24px_rgba(28,42,69,0.06)] sm:p-7">
      <div>
        <h2 id="ask-title" className="font-serif text-2xl font-semibold">Ask, or tell us something new</h2>
        <p className="mt-1 text-ink-soft">Exa looks answers up live (permits and benefits only from Migri, Kela, InfoFinland and Työmarkkinatori). If you mention something new, like “I&apos;ve been here 3 years”, your roadmap updates.</p>
      </div>
      <form onSubmit={(e) => { e.preventDefault(); ask(); }} className="flex flex-wrap gap-3">
        <label htmlFor="ask-input" className="sr-only">Your question</label>
        <input id="ask-input" value={q} onChange={(e) => setQ(e.target.value)} disabled={busy}
          placeholder="For example: Can I work part-time while I look? Or: I've actually been here 3 years."
          className="min-h-12 min-w-0 flex-1 rounded-xl border border-ink/25 bg-card px-4 text-lg" />
        <Button type="submit" disabled={busy || !q.trim()}>{busy ? "Looking it up…" : "Ask"}</Button>
      </form>
      {busy && <p role="status" className="flex items-center gap-2 text-sm text-ink-soft"><GlobeIcon className="h-4 w-4 text-verified" /> Exa is looking this up…</p>}
      {error && <GentleWarning>Couldn&apos;t get an answer right now. Please try again in a moment.</GentleWarning>}
      <ol className="space-y-5">
        {[...entries].reverse().slice(0, showAll ? undefined : 2).map((e, k) => {
          const i = entries.length - 1 - k;
          return (
            <li key={i} className="animate-fade-up rounded-2xl border border-rule bg-paper p-4">
              <p className="text-sm text-ink-soft">{e.question}</p>
              <p className="mt-2 text-lg">{e.res.answer}</p>
              {e.res.facts_update && Object.keys(e.res.facts_update).length > 0 && (
                <p className="mt-2 rounded-lg bg-accent-soft px-3 py-2 text-accent-ink">
                  Updated your situation: {Object.keys(e.res.facts_update).map((k) => k.replaceAll("_", " ")).join(", ")}.
                  Your roadmap was rebuilt.
                </p>
              )}
              {e.res.sources.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {e.res.sources.map((s) => <SourceChip key={s.url} live source={{ title: s.title, url: s.url, published: s.date }} />)}
                </div>
              )}
              {e.res.suggested_roadmap_step && !e.res.off_topic && (
                <div className="mt-3">
                  {e.added ? (
                    <p className="text-sm font-bold text-verified">✓ Added to {STEP_NAME[e.res.suggested_roadmap_step]}</p>
                  ) : (
                    <Button variant="chip" onClick={() => onAdd(i)}>Add to my roadmap · {STEP_NAME[e.res.suggested_roadmap_step]}</Button>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ol>
      {entries.length > 2 && (
        <Button variant="quiet" onClick={() => setShowAll(!showAll)}>{showAll ? "Show fewer answers" : `Show all ${entries.length} answers`}</Button>
      )}
    </section>
  );
}
