"use client";

import { useEffect, useState } from "react";
import type { AskSource, Deadline, Facts, PlanResponse, Source } from "@/lib/api";
import { FIELDS, display } from "@/lib/facts";
import { ago } from "@/lib/format";
import { firstSentence } from "@/lib/roadmap";
import { flattenSteps, type StepItem } from "@/lib/steps";
import { CheckIcon, GlobeIcon, PersonIcon, SearchIcon } from "./icons";
import { Button, GentleWarning, SourceChip, cx, formatDate, hostOf } from "./primitives";

export type AddedItem = { question: string; answer: string; sources: AskSource[] };

/** "Registration instructions … - Job Market Finland" -> "Registration instructions …", max ~45 characters. */
function shortTitle(title: string) {
  const first = title.split(/\s[-|–—]\s/)[0].trim() || title;
  return first.length > 45 ? first.slice(0, 44).replace(/\s\S*$/, "") + "…" : first;
}

/** A small source chip: short title and site. Hover or keyboard focus shows the full title, the sentence Exa
 *  highlighted on the page and how fresh it is. */
function SourceLink({ s, live }: { s: Source; live: boolean }) {
  const quote = firstSentence(s.highlight);
  const fresh = ago(s.published);
  return (
    <span className="group relative inline-flex">
      <a href={s.url} target="_blank" rel="noreferrer" title={s.title}
        className="inline-flex min-h-9 max-w-full items-center gap-1.5 rounded-full border border-rule bg-paper px-3 py-1 text-sm hover:border-ink">
        {live && <GlobeIcon className="h-3.5 w-3.5 shrink-0 text-verified" />}
        <span className="truncate font-bold">{shortTitle(s.title)}</span>
        <span className="shrink-0 text-ink-soft">· {hostOf(s.url)}</span>
        <span className="sr-only"> (opens in a new tab){quote ? `. Quote: ${quote}` : ""}</span>
      </a>
      <span role="tooltip" aria-hidden
        className="pointer-events-none invisible absolute bottom-full left-0 z-20 mb-2 w-[min(22rem,80vw)] rounded-xl border border-rule bg-card p-3 text-sm opacity-0 shadow-lg transition-opacity group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100">
        <span className="block font-bold">{s.title}</span>
        {quote && <span className="mt-1 block font-serif">“{quote}”</span>}
        <span className="mt-1 block text-ink-soft">{hostOf(s.url)}{fresh ? ` · updated ${fresh}` : ""}</span>
      </span>
    </span>
  );
}

function Quotes({ sources, live }: { sources: Source[]; live: boolean }) {
  if (!sources.length) return null;
  return <div className="mt-3 flex flex-wrap gap-2">{sources.map((s) => <SourceLink key={s.url} s={s} live={live} />)}</div>;
}

function Added({ items }: { items?: AddedItem[] }) {
  if (!items?.length) return null;
  return (
    <div className="mt-4 space-y-3">
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

/** How long you can stay, said gently (no "deadline"). The date always comes from the rules engine. */
function StayHeader({ d, note, onPickExactDate }: { d: Deadline; note?: string | null; onPickExactDate: () => void }) {
  const date = d.deadline_date ? `${d.deadline_is_approximate ? "around " : ""}${formatDate(d.deadline_date)}` : null;
  return (
    <section id="step-deadline" aria-label="How long you can stay" className="scroll-mt-24 space-y-3 rounded-3xl border border-rule bg-card p-5 sm:p-7">
      {date ? (
        <>
          <p className="text-lg text-ink-soft">You can stay in Finland to look for work until</p>
          <p className="font-serif text-4xl font-semibold leading-tight sm:text-5xl">{date}</p>
          {d.days_left !== null && d.days_left !== undefined && (
            <p className="text-lg">
              {d.days_left < 0 ? "This date has passed. Contact Migri today: there may still be options."
                : d.days_left < 14 ? `That's ${d.days_left} days from now.` : `That's ${d.deadline_is_approximate ? "about " : ""}${Math.round(d.days_left / 7)} weeks from now.`}
            </p>
          )}
          {d.deadline_is_approximate && (
            <p className="text-ink-soft">
              Based on an approximate last day of work.{" "}
              <button onClick={onPickExactDate} className="min-h-9 font-bold text-ink underline">Pick the exact date</button>
            </p>
          )}
        </>
      ) : d.possible_dates.length > 0 ? (
        <>
          <p className="font-serif text-2xl font-semibold">How long you can stay depends on one detail</p>
          <ul className="space-y-1 text-lg">
            {d.possible_dates.map((p) => (
              <li key={p.rule_id}><span className="font-serif font-semibold">{p.months} months</span>{p.deadline_date && <>: until {formatDate(p.deadline_date)}</>}</li>
            ))}
          </ul>
        </>
      ) : (
        <p className="font-serif text-2xl font-semibold">
          {d.status === "not_applicable" ? "Your right to stay doesn't depend on this job." : "We need one more detail to work out how long you can stay."}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
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
      </div>
      {d.check_status === "mismatch" && (
        <GentleWarning>{d.warning} <a href={d.warning_link ?? d.source.url} target="_blank" rel="noreferrer" className="font-bold underline">Check Migri</a></GentleWarning>
      )}
      <details className="text-ink-soft">
        <summary className="min-h-9 cursor-pointer font-bold text-ink">Why this date?</summary>
        <p className="mt-2">{d.explanation}</p>
        <Quotes sources={[d.source]} live={d.check_status === "verified"} />
      </details>
      {note && <p className="text-ink-soft">{note}</p>}
    </section>
  );
}

/** "Add info about this step": what the person types rewrites this step and the ones after it. */
function AddInfo({ step, disabled, onSubmit }: { step: StepItem; disabled: boolean; onSubmit: (note: string) => void }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const id = `info-${step.n}`;
  if (!open)
    return (
      <Button variant="quiet" disabled={disabled} onClick={() => setOpen(true)}>+ Add info about this step</Button>
    );
  return (
    <form className="mt-2 space-y-2" onSubmit={(e) => { e.preventDefault(); if (text.trim()) { onSubmit(text.trim()); setOpen(false); setText(""); } }}>
      <label htmlFor={id} className="block font-bold">What should we know about step {step.n}?</label>
      <textarea id={id} rows={2} value={text} autoFocus maxLength={500} onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
        placeholder="For example: I already registered last week. Or: I'm in an unemployment fund through my union."
        className="w-full rounded-xl border border-ink/25 bg-card p-3" />
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" disabled={disabled || !text.trim()}>Update this step and the next ones</Button>
        <Button type="button" variant="quiet" onClick={() => setOpen(false)}>Cancel</Button>
      </div>
    </form>
  );
}

export type Proposal = {
  n: number; // the step the info was added to
  note: string;
  plan: PlanResponse;
  facts: Facts;
  factsUpdate: Partial<Facts>;
  mock: boolean;
  message?: string;
};

const same = (a?: StepItem, b?: StepItem) =>
  !!a && !!b && a.title === b.title && (a.why ?? "") === (b.why ?? "") && a.points.join("|") === b.points.join("|");

function StepSummary({ s, live }: { s: StepItem; live?: boolean }) {
  return (
    <div className="min-w-0">
      <p className="font-serif text-lg font-semibold">{s.title}</p>
      {s.why && <p className="mt-1">{s.why}</p>}
      {s.points.length > 0 && <ul className="mt-2 list-disc space-y-1 pl-5">{s.points.map((p, j) => <li key={j}>{p}</li>)}</ul>}
      {live !== undefined && <Quotes sources={s.sources} live={live} />}
    </div>
  );
}

/** Before anything changes: what's there now next to what it would become, from step n on. Accept or keep. */
function Review({ p, current, currentDeadline, onAccept, onDiscard }: {
  p: Proposal; current: StepItem[]; currentDeadline?: Deadline; onAccept: () => void; onDiscard: () => void;
}) {
  const next = flattenSteps(p.plan);
  const rows: { n: number; now?: StepItem; after?: StepItem }[] = [];
  for (let n = p.n; n <= Math.max(current.length, next.length); n++)
    rows.push({ n, now: current.find((x) => x.n === n), after: next.find((x) => x.n === n) });
  const changed = rows.filter((r) => !same(r.now, r.after));
  const facts = Object.keys(p.factsUpdate)
    .map((k) => FIELDS.find((f) => f.id === k))
    .filter((f): f is (typeof FIELDS)[number] => !!f)
    .map((f) => display(f, p.facts[f.id], p.facts) ?? f.label);
  const oldDate = currentDeadline?.deadline_date, newDate = p.plan.deadline?.deadline_date;
  const dateChanged = !!newDate && oldDate !== newDate;
  const nothing = !changed.length && !facts.length && !dateChanged;

  return (
    <section aria-labelledby="review-title" className="animate-fade-up space-y-4 rounded-3xl border-2 border-accent/60 bg-card p-5 sm:p-7">
      <div>
        <h3 id="review-title" className="font-serif text-2xl font-semibold">Review the change from step {p.n}</h3>
        <p className="mt-1 text-ink-soft">You added: “{p.note}”. Nothing changes until you choose.</p>
      </div>
      {p.message && <p className="rounded-lg bg-accent-soft px-3 py-2 text-accent-ink">{p.message}</p>}
      {facts.length > 0 && (
        <p><span className="font-bold">We&apos;ll also note: </span>{facts.join(" · ")}</p>
      )}
      {dateChanged && (
        <p><span className="font-bold">The date you can stay until changes: </span>
          {oldDate ? formatDate(oldDate) : "not known"} → <strong>{formatDate(newDate!)}</strong></p>
      )}
      {nothing && <p>Your steps stay the same with this information.</p>}
      {changed.length > 0 && (
        <ol className="space-y-3">
          {changed.map((r) => (
            <li key={r.n} className="rounded-2xl border border-rule bg-paper p-4">
              <p className="text-sm font-bold text-accent-ink">Step {r.n}</p>
              <div className="mt-2 grid gap-4 sm:grid-cols-2">
                <div className="min-w-0 text-ink-soft">
                  <p className="mb-1 text-xs font-bold uppercase tracking-wide">Now</p>
                  {r.now ? <div className="line-through decoration-ink-soft/50"><StepSummary s={r.now} /></div> : <p>No step here yet</p>}
                </div>
                <div className="min-w-0 rounded-xl border-l-4 border-accent pl-3">
                  <p className="mb-1 text-xs font-bold uppercase tracking-wide text-accent-ink">After the change</p>
                  {r.after ? <StepSummary s={r.after} live={!p.plan.mock} /> : <p className="text-ink-soft">This step is removed</p>}
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
      <div className="flex flex-wrap gap-3">
        <Button onClick={onAccept}>{nothing ? "OK" : changed.length ? "Use the new steps" : "Save this"}</Button>
        {!nothing && <Button variant="quiet" onClick={onDiscard}>Keep my current steps</Button>}
      </div>
    </section>
  );
}

export function Steps({
  plan, deadline, live, done, added, updatingFrom, message, searchingText, onToggleDone, onAddInfo, onPickExactDate, focus,
  proposal, onAccept, onDiscard,
}: {
  plan?: PlanResponse;
  deadline?: Deadline;
  live: boolean;
  done: Record<string, boolean>;
  added: Partial<Record<"week1" | "deadline", AddedItem[]>>;
  updatingFrom: number | null;
  message?: { n: number; text: string } | null;
  searchingText?: string;
  onToggleDone: (key: string) => void;
  onAddInfo: (n: number, note: string) => void;
  onPickExactDate: () => void;
  focus?: { id: "week1" | "deadline"; at: number } | null; // scroll to and briefly highlight
  proposal?: Proposal | null; // a change waiting for the person to accept or keep
  onAccept: () => void;
  onDiscard: () => void;
}) {
  const steps = flattenSteps(plan);
  const lastThisWeek = steps.filter((s) => s.kind === "action").at(-1)?.n;
  const [flash, setFlash] = useState<string | null>(null);
  useEffect(() => {
    if (!focus) return;
    setFlash(focus.id);
    const t1 = setTimeout(() => document.getElementById(`step-${focus.id}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    const t2 = setTimeout(() => setFlash(null), 2500);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [focus]);

  return (
    <div className="space-y-6">
      {deadline && (
        <div className={cx("rounded-3xl transition-colors duration-700", flash === "deadline" && "bg-accent-soft/70")}>
          <StayHeader d={deadline} note={plan && !plan.plan_b.length ? plan.plan_b_note : null} onPickExactDate={onPickExactDate} />
          <Added items={added.deadline} />
        </div>
      )}
      <ol aria-label="Your steps" className="space-y-4">
        {steps.filter((s) => !proposal || s.n < proposal.n).map((s) => {
          const updating = updatingFrom !== null && s.n >= updatingFrom;
          const isDone = !!done[s.key];
          return (
            <li key={s.key} id={s.n === 1 ? "step-week1" : undefined}
              className={cx("animate-fade-up scroll-mt-24 rounded-2xl border bg-card p-4 transition-colors duration-700 sm:p-6",
                updating ? "border-accent/60" : "border-rule", flash === "week1" && s.kind === "action" && "bg-accent-soft/70")}>
              <div className="flex items-start gap-4">
                <span aria-hidden className={cx("flex h-10 w-10 shrink-0 items-center justify-center rounded-full font-serif text-lg font-semibold",
                  isDone ? "bg-verified text-paper" : "bg-accent-soft text-accent-ink")}>
                  {isDone ? <CheckIcon className="h-4 w-4" /> : s.n}
                </span>
                <div className={cx("min-w-0 flex-1", updating && "opacity-50")}>
                  <p className="text-sm font-bold text-accent-ink">Step {s.n}</p>
                  <h3 className={cx("font-serif text-xl font-semibold sm:text-2xl", isDone && "text-ink-soft line-through")}>{s.title}</h3>
                  {s.why && <p className="mt-1">{s.why}</p>}
                  {s.points.length > 0 && <ul className="mt-2 list-disc space-y-1 pl-5">{s.points.map((p, j) => <li key={j}>{p}</li>)}</ul>}
                  <Quotes sources={s.sources} live={live} />
                  {s.n === lastThisWeek && <Added items={added.week1} />}
                </div>
              </div>
              <div className="mt-3 space-y-2 pl-14">
                {updating && (
                  <p role="status" className="flex items-center gap-2 text-ink-soft">
                    <SearchIcon /> {s.n === updatingFrom ? `${searchingText ?? "Exa is checking this again"}…` : "May change with what you added…"}
                  </p>
                )}
                {message && message.n === s.n && !updating && <p className="rounded-lg bg-accent-soft px-3 py-2 text-accent-ink">{message.text}</p>}
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                  <label className="inline-flex min-h-11 cursor-pointer items-center gap-2">
                    <input type="checkbox" checked={isDone} onChange={() => onToggleDone(s.key)} className="h-5 w-5 accent-[var(--color-verified)]" />
                    Done
                  </label>
                  <AddInfo step={s} disabled={updatingFrom !== null || !!proposal} onSubmit={(note) => onAddInfo(s.n, note)} />
                </div>
              </div>
            </li>
          );
        })}
      </ol>
      {proposal && <Review p={proposal} current={steps} currentDeadline={deadline} onAccept={onAccept} onDiscard={onDiscard} />}
    </div>
  );
}

export function Legend() {
  return (
    <section aria-label="Legend" className="flex flex-wrap gap-x-6 gap-y-2 border-t border-rule pt-5 text-sm text-ink-soft">
      <span className="inline-flex items-center gap-1.5"><PersonIcon className="h-4 w-4 text-accent-ink" /> From your answers</span>
      <span className="inline-flex items-center gap-1.5"><GlobeIcon className="h-4 w-4 text-verified" /> Found live on the web by Exa</span>
      <span className="inline-flex items-center gap-1.5">Saved guide = our checked fallback</span>
    </section>
  );
}
