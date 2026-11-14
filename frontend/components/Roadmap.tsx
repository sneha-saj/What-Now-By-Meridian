"use client";

import { useState } from "react";
import type { Deadline, Facts, PlanResponse, ReferralResponse, Source } from "@/lib/api";
import { FIELDS, display, formatShortDate } from "@/lib/facts";
import { firstSentence, timelineFor, type NodeId, type RoadNode } from "@/lib/roadmap";
import { FindYourWayIn } from "./FindYourWayIn";
import { CheckIcon, GlobeIcon, PersonIcon, SearchIcon } from "./icons";
import { GentleWarning, cx, formatDate, hostOf } from "./primitives";

/** A source with the sentence Exa highlighted on the page. */
function SourceQuote({ s, live }: { s: Source; live: boolean }) {
  const quote = firstSentence(s.highlight);
  return (
    <figure className="rounded-xl border border-rule bg-paper p-3">
      {quote && <blockquote className="font-serif text-[1.05rem] leading-relaxed">“{quote}”</blockquote>}
      <figcaption className={cx("flex flex-wrap items-center gap-x-2 gap-y-1 text-sm", quote && "mt-2")}>
        {live ? <GlobeIcon className="h-4 w-4 text-verified" /> : null}
        <a href={s.url} target="_blank" rel="noreferrer" className="font-bold underline decoration-rule underline-offset-4 hover:decoration-ink">
          {s.title}<span className="sr-only"> (opens in a new tab)</span>
        </a>
        <span className="text-ink-soft">
          · {live ? `found live on ${hostOf(s.url)}` : hostOf(s.url)}
          {s.published ? ` · page from ${formatShortDate(s.published)}` : ""}
        </span>
      </figcaption>
    </figure>
  );
}

function Quotes({ sources, live }: { sources: Source[]; live: boolean }) {
  if (!sources.length) return null;
  return <div className="mt-3 space-y-2">{sources.map((s) => <SourceQuote key={s.url} s={s} live={live} />)}</div>;
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
  if (n.id === "today")
    return <p className="flex items-center gap-1.5 text-ink-soft"><PersonIcon /> From your answers</p>;
  if (n.state === "done")
    return <p className="flex items-center gap-1.5 font-bold text-verified"><CheckIcon /> Done</p>;
  if (n.source)
    return (
      <p className="flex flex-wrap items-center gap-1.5 text-ink-soft">
        {n.live ? <><GlobeIcon className="h-4 w-4 text-verified" /> Found live on {hostOf(n.source.url)}</> : <>From {hostOf(n.source.url)} (saved guide)</>}
        {n.source.published && <> · page from {formatShortDate(n.source.published)}</>}
      </p>
    );
  return null;
}

const WHY: Partial<Record<NodeId, string>> = {
  week1: "These keep your money and your options open while you look for work.",
  week2: "Most jobs in Finland are found through people. A short, friendly message goes a long way.",
  week4: "A month in is a good moment to widen your search to sectors that are short of workers.",
  week8: "Two months in, check your plan and your backup options so nothing comes as a surprise.",
  final: "If a new job doesn't come in time, these are the other ways to stay. Start them early.",
};

function DeadlineBody({ d }: { d: Deadline }) {
  return (
    <div className="space-y-4">
      {d.deadline_date ? (
        <div>
          <p className="font-serif text-5xl font-semibold leading-tight sm:text-6xl">{formatDate(d.deadline_date)}</p>
          {d.days_left !== null && d.days_left !== undefined && (
            <p className="mt-2 text-xl">
              {d.days_left < 0 ? "This date has passed. Contact Migri today: there may still be options."
                : d.days_left < 14 ? `That's ${d.days_left} days from now.` : `That's ${Math.round(d.days_left / 7)} weeks from now.`}
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
  referrals?: ReferralResponse;
  doneActions: Record<number, boolean>;
  doneNodes: Partial<Record<NodeId, boolean>>;
  drafts: Record<string, string>;
};

export function Roadmap({
  nodes, data, onToggleAction, onToggleNode, onDraft,
}: {
  nodes: RoadNode[];
  data: RoadmapData;
  onToggleAction: (i: number) => void;
  onToggleNode: (id: NodeId) => void;
  onDraft: (url: string, text: string) => void;
}) {
  const [open, setOpen] = useState<Partial<Record<NodeId, boolean>>>({ week1: true, deadline: true });
  const { plan, referrals, deadline, facts } = data;
  const planLive = !!plan && !plan.mock;

  function body(n: RoadNode) {
    if (n.id === "today")
      return (
        <ul className="flex flex-wrap gap-2">
          {FIELDS.map((f) => display(f, facts[f.id])).filter(Boolean).map((t) => (
            <li key={t} className="inline-flex items-center gap-1.5 rounded-full border border-ink/15 bg-paper px-3 py-1"><PersonIcon className="h-3.5 w-3.5 text-accent-ink" />{t}</li>
          ))}
        </ul>
      );
    if (n.id === "deadline" && deadline) return <DeadlineBody d={deadline} />;
    if (n.id === "week1" && plan)
      return (
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
      );
    const t = timelineFor(plan, n.id === "final" ? "Final weeks" : n.label);
    return (
      <div className="space-y-5">
        {WHY[n.id] && <p className="text-ink-soft">{WHY[n.id]}</p>}
        {t && (
          <>
            <ul className="list-disc space-y-1 pl-5">{t.steps.map((s, j) => <li key={j}>{s}</li>)}</ul>
            <Quotes sources={t.sources} live={planLive} />
          </>
        )}
        {n.id === "week2" && referrals && <FindYourWayIn r={referrals} drafts={data.drafts} onDraft={onDraft} bare />}
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
        <label className="inline-flex min-h-11 cursor-pointer items-center gap-3">
          <input type="checkbox" checked={!!data.doneNodes[n.id]} onChange={() => onToggleNode(n.id)} className="h-6 w-6 accent-[var(--color-verified)]" />
          Mark this step as done
        </label>
      </div>
    );
  }

  return (
    <section aria-labelledby="roadmap-title">
      <h2 id="roadmap-title" className="font-serif text-3xl font-semibold sm:text-4xl">Your roadmap</h2>
      <ol className="relative mt-6">
        {/* the amber line from Today to Your deadline */}
        <span aria-hidden className="animate-draw-down absolute bottom-6 left-[13px] top-3 w-[2px] rounded bg-accent/70" />
        {nodes.map((n) => {
          const isEnd = n.id === "deadline";
          const expanded = !!open[n.id] && n.state !== "searching";
          const panelId = `node-${n.id}`;
          return (
            <li key={n.id} className="animate-fade-up relative grid grid-cols-[28px_1fr] gap-x-4 pb-8 last:pb-0">
              <div className="flex justify-center pt-1.5"><Dot state={n.state} isEnd={isEnd} /></div>
              <div className="min-w-0">
                <button
                  onClick={() => setOpen({ ...open, [n.id]: !open[n.id] })}
                  aria-expanded={expanded}
                  aria-controls={panelId}
                  disabled={n.state === "searching"}
                  className="w-full rounded-xl text-left disabled:cursor-default"
                >
                  <p className="text-sm font-bold text-accent-ink">
                    {n.label}{n.startsOn && n.id !== "today" && !isEnd ? ` · from ${formatShortDate(n.startsOn.toISOString().slice(0, 10))}` : ""}
                  </p>
                  <p className={cx("font-serif font-semibold", isEnd ? "text-2xl" : "text-xl sm:text-2xl", n.state === "done" && "text-ink-soft")}>
                    {n.title}
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
      <span className="inline-flex items-center gap-1.5"><span className="h-3 w-3 rounded-full bg-verified" /> Done by you</span>
    </section>
  );
}
