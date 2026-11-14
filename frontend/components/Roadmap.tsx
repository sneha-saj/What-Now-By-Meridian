"use client";

import { useEffect, useState } from "react";
import type { AskSource, Deadline, Facts, PlanResponse, Source } from "@/lib/api";
import { FIELDS, display, formatShortDate } from "@/lib/facts";
import { ago } from "@/lib/format";
import { firstSentence, timelineFor, type LiveFind, type NodeId, type RoadNode } from "@/lib/roadmap";
import { CheckIcon, GlobeIcon, PersonIcon, SearchIcon } from "./icons";
import { GentleWarning, SourceChip, cx, formatDate, hostOf } from "./primitives";

export type AddedItem = { question: string; answer: string; sources: AskSource[] };

/** A source with the sentence Exa highlighted on the page, and how fresh the page is. */
function SourceQuote({ s, live }: { s: Source; live: boolean }) {
  const quote = firstSentence(s.highlight);
  const fresh = ago(s.published);
  return (
    <figure className="rounded-xl border border-rule bg-paper p-3">
      {quote && <blockquote className="font-serif text-[1.05rem] leading-relaxed">“{quote}”</blockquote>}
      <figcaption className={cx("flex flex-wrap items-center gap-x-2 gap-y-1 text-sm", quote && "mt-2")}>
        {live && <GlobeIcon className="h-4 w-4 text-verified" />}
        <a href={s.url} target="_blank" rel="noreferrer" className="font-bold underline decoration-rule underline-offset-4 hover:decoration-ink">
          {s.title}<span className="sr-only"> (opens in a new tab)</span>
        </a>
        <span className="text-ink-soft">· {hostOf(s.url)}{fresh ? ` · updated ${fresh}` : ""}</span>
      </figcaption>
    </figure>
  );
}

function Quotes({ sources, live }: { sources: Source[]; live: boolean }) {
  if (!sources.length) return null;
  return <div className="mt-3 space-y-2">{sources.map((s) => <SourceQuote key={s.url} s={s} live={live} />)}</div>;
}

/** The live, specific item for a step, highlighted so it's obvious it came from Exa. */
function LiveFindCallout({ f }: { f: LiveFind }) {
  const when = ago(f.date);
  return (
    <a href={f.url} target="_blank" rel="noreferrer"
      className="flex items-start gap-3 rounded-2xl border border-verified/30 bg-verified-soft/60 p-4 hover:border-verified">
      <GlobeIcon className="mt-0.5 h-5 w-5 text-verified" />
      <span className="min-w-0">
        <span className="block text-sm font-bold text-verified">Found live by Exa{f.note ? ` · ${f.note}` : ""}</span>
        <span className="block font-bold underline decoration-verified/40 underline-offset-4">{f.label}</span>
        <span className="block text-sm text-ink-soft">{hostOf(f.url)}{when ? ` · updated ${when}` : ""}</span>
        <span className="sr-only">(opens in a new tab)</span>
      </span>
    </a>
  );
}

function Dot({ state, isEnd }: { state: RoadNode["state"]; isEnd?: boolean }) {
  return (
    <span aria-hidden className={cx(
      "relative z-10 flex items-center justify-center rounded-full",
      isEnd ? "h-7 w-7" : "h-5 w-5",
      state === "searching" && "border-2 border-dashed border-accent bg-paper motion-safe:animate-pulse",
      state === "found" && (isEnd ? "bg-ink" : "border-2 border-accent bg-accent"),
      state === "done" && "bg-verified text-paper",
    )}>
      {state === "done" && <CheckIcon className="h-3 w-3" />}
    </span>
  );
}

function StatusLine({ n }: { n: RoadNode }) {
  if (n.state === "searching")
    return <p className="flex items-center gap-1.5 text-ink-soft"><SearchIcon /> {n.searchingText ?? "Searching"}…</p>;
  if (n.id === "today") return <p className="flex items-center gap-1.5 text-ink-soft"><PersonIcon /> From your answers</p>;
  const done = n.state === "done" && <span className="inline-flex items-center gap-1 font-bold text-verified"><CheckIcon /> Done ·</span>;
  if (n.liveFind) {
    const when = ago(n.liveFind.date);
    return (
      <p className="flex flex-wrap items-center gap-1.5 text-ink-soft">
        {done}<GlobeIcon className="h-4 w-4 text-verified" />
        <span>Found live on {hostOf(n.liveFind.url)}{when ? ` · updated ${when}` : ""}</span>
      </p>
    );
  }
  return <p className="flex flex-wrap items-center gap-1.5 text-ink-soft">{done}<span>Saved guide</span></p>;
}

const WHY: Partial<Record<NodeId, string>> = {
  week1: "These keep your money and your options open while you look for work.",
  week2: "Keep your search going: apply, follow up and keep your CV current.",
  week4: "A month in is a good moment to widen your search to sectors that are short of workers.",
  week8: "Two months in, check your plan and your backup options so nothing comes as a surprise.",
  final: "If a new job doesn't come in time, these are the other ways to stay. Start them early.",
};

function deadlineTitle(d?: Deadline) {
  if (!d?.deadline_date) return null;
  return `${d.deadline_is_approximate ? "Around " : ""}${formatDate(d.deadline_date)}`;
}

function DeadlineBody({ d, onPickExactDate }: { d: Deadline; onPickExactDate: () => void }) {
  return (
    <div className="space-y-4">
      {d.deadline_date ? (
        <div>
          <p className="font-serif text-5xl font-semibold leading-tight sm:text-6xl">{deadlineTitle(d)}</p>
          {d.days_left !== null && d.days_left !== undefined && (
            <p className="mt-2 text-xl">
              {d.days_left < 0 ? "This date has passed. Contact Migri today: there may still be options."
                : d.days_left < 14 ? `That's ${d.days_left} days from now.` : `That's ${d.deadline_is_approximate ? "about " : ""}${Math.round(d.days_left / 7)} weeks from now.`}
            </p>
          )}
          {d.deadline_is_approximate && (
            <p className="mt-2 text-ink-soft">
              Based on an approximate last day of work.{" "}
              <button onClick={onPickExactDate} className="min-h-9 font-bold text-ink underline">Pick the exact date</button>
            </p>
          )}
        </div>
      ) : d.possible_dates.length > 0 ? (
        <div>
          <p className="font-serif text-3xl font-semibold">It depends on one detail</p>
          <ul className="mt-2 space-y-1 text-xl">
            {d.possible_dates.map((p) => (
              <li key={p.rule_id}><span className="font-serif font-semibold">{p.months} months</span>{p.deadline_date && <> → {formatDate(p.deadline_date)}</>}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="font-serif text-3xl font-semibold">{d.status === "not_applicable" ? "Your permit doesn't depend on this job." : "We need one more detail."}</p>
      )}

      {d.check_status === "verified" && (
        <a href="/how-we-know" className="inline-flex min-h-9 flex-wrap items-center gap-1.5 rounded-full bg-verified-soft px-3 py-1 font-bold text-verified hover:underline">
          <CheckIcon /> Checked against migri.fi today{d.rule_in_force_since && <span className="font-normal">· rule since {formatDate(d.rule_in_force_since)}</span>}
        </a>
      )}
      {d.check_status === "error" && (
        <p className="inline-flex min-h-9 items-center gap-2 rounded-full bg-paper-deep px-3 py-1 text-ink-soft">
          Couldn&apos;t check migri.fi right now · <a href="/how-we-know" className="underline">how we check</a>
        </p>
      )}
      {d.check_status === "mismatch" && (
        <GentleWarning>{d.warning} <a href={d.warning_link ?? d.source.url} target="_blank" rel="noreferrer" className="font-bold underline">Check Migri</a></GentleWarning>
      )}
      <p className="max-w-2xl text-lg">{d.explanation}</p>
      <Quotes sources={[d.source]} live={d.check_status === "verified"} />
    </div>
  );
}

export type RoadmapData = {
  facts: Facts;
  deadline?: Deadline;
  plan?: PlanResponse;
  doneActions: Record<number, boolean>;
  doneNodes: Partial<Record<NodeId, boolean>>;
  added: Partial<Record<NodeId, AddedItem[]>>;
};

export function Roadmap({
  nodes, data, onToggleAction, onToggleNode, onPickExactDate, focus,
}: {
  nodes: RoadNode[];
  data: RoadmapData;
  onToggleAction: (i: number) => void;
  onToggleNode: (id: NodeId) => void;
  onPickExactDate: () => void;
  focus?: { id: NodeId; at: number } | null; // open, scroll to and briefly highlight this step
}) {
  const [open, setOpen] = useState<Partial<Record<NodeId, boolean>>>({ week1: true });
  const [flash, setFlash] = useState<NodeId | null>(null);
  useEffect(() => {
    if (!focus) return;
    setOpen((o) => ({ ...o, [focus.id]: true }));
    setFlash(focus.id);
    const t1 = setTimeout(() => document.getElementById(`step-${focus.id}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    const t2 = setTimeout(() => setFlash(null), 2500);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [focus]);
  const { plan, deadline, facts } = data;
  const planLive = !!plan && !plan.mock;

  function added(id: NodeId) {
    const items = data.added[id];
    if (!items?.length) return null;
    return (
      <div className="space-y-3">
        <p className="font-bold">From your questions</p>
        {items.map((a, k) => (
          <div key={k} className="rounded-xl border border-rule bg-paper p-3">
            <p className="text-sm text-ink-soft">{a.question}</p>
            <p className="mt-1">{a.answer}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {a.sources.map((s) => <SourceChip key={s.url} live source={{ title: s.title, url: s.url, published: s.date }} />)}
            </div>
          </div>
        ))}
      </div>
    );
  }

  function body(n: RoadNode) {
    if (n.id === "today")
      return (
        <ul className="flex flex-wrap gap-2">
          {FIELDS.map((f) => display(f, facts[f.id])).filter(Boolean).map((t) => (
            <li key={t} className="inline-flex items-center gap-1.5 rounded-full border border-ink/15 bg-paper px-3 py-1"><PersonIcon className="h-3.5 w-3.5 text-accent-ink" />{t}</li>
          ))}
        </ul>
      );
    if (n.id === "deadline" && deadline)
      return (
        <div className="space-y-6">
          <DeadlineBody d={deadline} onPickExactDate={onPickExactDate} />
          {plan && (plan.plan_b.length > 0 || plan.plan_b_note) && (
            <div className="space-y-3">
              <h3 className="font-serif text-2xl font-semibold">If no job comes in time: Plan B</h3>
              {plan.plan_b.length ? (
                <ul className="space-y-4">
                  {plan.plan_b.map((p) => (
                    <li key={p.id || p.option} className="rounded-2xl border border-rule bg-card p-4 sm:p-5">
                      <p className="font-serif text-xl font-semibold">{p.option}</p>
                      {p.who_it_fits && <p className="mt-1"><span className="text-ink-soft">Who it fits: </span>{p.who_it_fits}</p>}
                      <p className="mt-1">{p.why}</p>
                      {p.latest_start_date && <p className="mt-1"><span className="text-ink-soft">Start by: </span><strong>{formatDate(p.latest_start_date)}</strong></p>}
                      <Quotes sources={p.sources} live={planLive} />
                    </li>
                  ))}
                </ul>
              ) : <p>{plan.plan_b_note}</p>}
            </div>
          )}
          {added("deadline")}
          {added("final")}
        </div>
      );
    const find = n.liveFind && n.id !== "deadline" ? <LiveFindCallout f={n.liveFind} /> : null;
    if (n.id === "week1" && plan)
      return (
        <div className="space-y-4">
          {find}
          <ol className="space-y-4">
            {plan.this_week.map((a, i) => (
              <li key={i} className="rounded-2xl border border-rule bg-card p-4 sm:p-5">
                <div className="flex items-start gap-3">
                  <input id={`a-${i}`} type="checkbox" checked={!!data.doneActions[i]} onChange={() => onToggleAction(i)}
                    className="mt-1.5 h-6 w-6 shrink-0 cursor-pointer accent-[var(--color-verified)]" />
                  <div className="min-w-0">
                    <label htmlFor={`a-${i}`} className={cx("cursor-pointer font-serif text-xl font-semibold", data.doneActions[i] && "text-ink-soft line-through")}>
                      {i + 1}. {a.title}
                    </label>
                    <p className="mt-1">{a.why}</p>
                    <ol className="mt-2 list-disc space-y-1 pl-5">{a.how.map((h, j) => <li key={j}>{h}</li>)}</ol>
                    <Quotes sources={a.sources} live={planLive} />
                  </div>
                </div>
              </li>
            ))}
          </ol>
          {added("week1")}
        </div>
      );
    const t = timelineFor(plan, n.id === "final" ? "Final weeks" : n.label);
    return (
      <div className="space-y-5">
        {WHY[n.id] && <p className="text-ink-soft">{WHY[n.id]}</p>}
        {find}
        {t && (
          <>
            <ul className="list-disc space-y-1 pl-5">{t.steps.map((s, j) => <li key={j}>{s}</li>)}</ul>
            <Quotes sources={t.sources} live={planLive} />
          </>
        )}
        {n.id === "final" && plan && (
          plan.plan_b.length ? (
            <ul className="space-y-4">
              {plan.plan_b.map((p) => (
                <li key={p.id || p.option} className="rounded-2xl border border-rule bg-card p-4 sm:p-5">
                  <p className="font-serif text-xl font-semibold">{p.option}</p>
                  {p.who_it_fits && <p className="mt-1"><span className="text-ink-soft">Who it fits: </span>{p.who_it_fits}</p>}
                  <p className="mt-1">{p.why}</p>
                  {p.latest_start_date && <p className="mt-1"><span className="text-ink-soft">Start by: </span><strong>{formatDate(p.latest_start_date)}</strong></p>}
                  <Quotes sources={p.sources} live={planLive} />
                </li>
              ))}
            </ul>
          ) : <p>{plan.plan_b_note}</p>
        )}
        {added(n.id)}
        <label className="inline-flex min-h-11 cursor-pointer items-center gap-3">
          <input type="checkbox" checked={!!data.doneNodes[n.id]} onChange={() => onToggleNode(n.id)} className="h-6 w-6 accent-[var(--color-verified)]" />
          Mark this step as done
        </label>
      </div>
    );
  }

  return (
    <section aria-label="Your roadmap">
      <ol className="relative">
        <span aria-hidden className="animate-draw-down absolute bottom-6 left-[13px] top-3 w-[2px] rounded bg-accent/70" />
        {nodes.map((n) => {
          const isEnd = n.id === "deadline";
          const expanded = !!open[n.id] && n.state !== "searching";
          const panelId = `node-${n.id}`;
          const title = isEnd ? deadlineTitle(deadline) ?? n.title : n.title;
          return (
            <li key={n.id} id={`step-${n.id}`} className={cx("animate-fade-up relative grid scroll-mt-24 grid-cols-[28px_1fr] gap-x-4 rounded-2xl pb-8 transition-colors duration-700 last:pb-0",
              flash === n.id && "bg-accent-soft/70")}>
              <div className="flex justify-center pt-1.5"><Dot state={n.state} isEnd={isEnd} /></div>
              <div className="min-w-0">
                <button
                  onClick={() => setOpen({ ...open, [n.id]: !open[n.id] })}
                  aria-expanded={expanded}
                  aria-controls={panelId}
                  disabled={n.state === "searching"}
                  className="w-full rounded-xl text-left disabled:cursor-default"
                >
                  <p className="text-sm font-bold text-accent-ink">{n.label}</p>
                  <p className={cx("font-serif font-semibold", isEnd ? "text-3xl" : "text-xl sm:text-2xl", n.state === "done" && "text-ink-soft")}>
                    {title}
                    {n.state !== "searching" && <span aria-hidden className="ml-2 text-base text-ink-soft">{expanded ? "−" : "+"}</span>}
                  </p>
                  <StatusLine n={n} />
                </button>
                {expanded && <div id={panelId} className="animate-fade-up mt-4">{body(n)}</div>}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export function Legend() {
  return (
    <section aria-label="Legend" className="flex flex-wrap gap-x-6 gap-y-2 border-t border-rule pt-5 text-sm text-ink-soft">
      <span className="inline-flex items-center gap-1.5"><PersonIcon className="h-4 w-4 text-accent-ink" /> From your answers</span>
      <span className="inline-flex items-center gap-1.5"><GlobeIcon className="h-4 w-4 text-verified" /> Found live on the web by Exa</span>
      <span className="inline-flex items-center gap-1.5"><SearchIcon /> Still searching</span>
      <span className="inline-flex items-center gap-1.5">Saved guide = our checked fallback</span>
    </section>
  );
}
