"use client";

import { useState } from "react";
import type { Question } from "@/lib/api";
import { Button, cx } from "./primitives";
import { RotatingPhrase } from "./RotatingPhrase";

/** One question at a time: serif question, tap buttons (incl. "Not sure"), or answer in your own words.
 *  `previous` is the answer already given when the person went back to this question: it's shown as chosen and
 *  can be changed. Back/Forward move through the questions answered so far. */
export function QuestionCard({
  question, busy, onAnswer, onText, previous, onBack, onForward, position,
}: {
  question: Question;
  busy?: boolean;
  onAnswer: (value: string) => void;
  onText: (text: string) => void;
  previous?: string;
  onBack?: () => void;
  onForward?: () => void;
  position?: string;
}) {
  const isOption = previous !== undefined && question.options.some((o) => o.value === previous);
  const [date, setDate] = useState(question.kind === "date" && previous && !isOption ? previous : "");
  const [text, setText] = useState(previous !== undefined && !isOption && question.kind !== "date" ? previous : "");
  const [picked, setPicked] = useState<string | null>(null);
  const choose = (value: string) => {
    setPicked(value);
    onAnswer(value);
  };
  return (
    <section aria-labelledby="q-title" className="animate-fade-up rounded-3xl border border-rule bg-card p-6 shadow-[0_6px_24px_rgba(28,42,69,0.06)] sm:p-8">
      <div className="flex items-center gap-3">
        {(onBack || onForward) && (
          <button type="button" onClick={onBack} disabled={!onBack || busy} aria-label="Previous question" title="Previous question"
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-rule text-lg text-ink hover:border-ink disabled:invisible"><span aria-hidden>←</span></button>
        )}
        <p className="min-w-0 flex-1 text-sm text-ink-soft">{position ?? "One quick question"}{previous !== undefined && " · your answer is marked; change it or go forward"}</p>
        {onForward && (
          <button type="button" onClick={onForward} disabled={busy} aria-label="Next question" title="Next question"
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-rule text-lg text-ink hover:border-ink disabled:invisible"><span aria-hidden>→</span></button>
        )}
      </div>
      <h2 id="q-title" className="mt-1 font-serif text-3xl font-semibold leading-snug sm:text-4xl">{question.question}</h2>
      <fieldset disabled={busy || picked !== null} className="mt-6 space-y-5">
        <legend className="sr-only">Choose an answer</legend>
        <div className="flex flex-wrap gap-3">
          {question.options.map((o) => {
            const chosen = picked === o.value || (picked === null && previous === o.value);
            return (
              <Button key={o.value} variant="chip" aria-pressed={chosen}
                className={cx("text-lg", chosen && "!border-ink !bg-ink !text-paper !opacity-100")}
                onClick={() => choose(o.value)}>
                {chosen && <span aria-hidden>✓</span>}
                {o.label}
              </Button>
            );
          })}
        </div>
        {picked !== null && (
          <p role="status" className="animate-fade-up text-ink-soft">Got it. Updating your situation…</p>
        )}
        {question.kind === "date" && (
          <form className="flex flex-wrap items-center gap-3" onSubmit={(e) => { e.preventDefault(); if (date) choose(date); }}>
            <label htmlFor="q-date" className="text-ink-soft">Or pick the exact date</label>
            <input id="q-date" type="date" value={date} onChange={(e) => setDate(e.target.value)}
              className="min-h-11 rounded-xl border border-ink/30 bg-card px-3" />
            <Button type="submit" variant="chip" disabled={!date}>Use this date</Button>
          </form>
        )}
        <form className="flex flex-wrap items-center gap-3" onSubmit={(e) => { e.preventDefault(); if (text.trim()) { setPicked(text.trim()); onText(text.trim()); setText(""); } }}>
          <label htmlFor="q-text" className="sr-only">Or answer in your own words</label>
          <input id="q-text" value={text} onChange={(e) => setText(e.target.value)} placeholder="Or answer in your own words"
            className="min-h-11 min-w-0 flex-1 rounded-xl border border-ink/25 bg-paper px-4" />
          <Button type="submit" variant="quiet" disabled={!text.trim()}>Send</Button>
        </form>
      </fieldset>
    </section>
  );
}

/** First screen: the warm opening line and one text box, plus any roadmaps saved in this browser. */
export function Welcome({ busy, onSubmit, saved = [], onOpen, onDelete, phrases = ["Lost your job?"] }: {
  busy?: boolean;
  /** Rotating first half of the headline. "Lost your job?" is what screen readers and reduced-motion users get. */
  phrases?: string[];
  onSubmit: (text: string) => void;
  saved?: { id: string; title: string; summary?: string[]; savedAt: string }[];
  onOpen?: (id: string) => void;
  onDelete?: (id: string) => void;
}) {
  const [text, setText] = useState("");
  const [holdHeadline, setHoldHeadline] = useState(false);
  return (
    <section aria-labelledby="welcome-title" className="animate-fade-up mx-auto max-w-3xl space-y-6 py-6 sm:py-12">
      <h1 id="welcome-title" className="font-serif text-4xl font-semibold leading-tight text-ink sm:text-6xl"
        onMouseEnter={() => setHoldHeadline(true)} onMouseLeave={() => setHoldHeadline(false)}
        onFocus={() => setHoldHeadline(true)} onBlur={() => setHoldHeadline(false)}>
        <span className="sr-only">Lost your job? Let&apos;s figure out what&apos;s next.</span>
        <RotatingPhrase phrases={phrases} interval={2000} paused={holdHeadline} staticPhrase="Lost your job?"
          className="text-accent-ink" />
        <span aria-hidden="true" className="block">Let&apos;s figure out what&apos;s next.</span>
      </h1>
      <p className="text-xl text-ink-soft">
        Tell me in a sentence or two what happened. I&apos;ll ask only what&apos;s missing, then give you your steps, in order, from
        official Finnish sources, found live.
      </p>
      <form onSubmit={(e) => { e.preventDefault(); if (text.trim()) onSubmit(text.trim()); }} className="space-y-4">
        <label htmlFor="welcome-text" className="sr-only">What happened?</label>
        <textarea id="welcome-text" rows={4} value={text} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (text.trim()) onSubmit(text.trim()); } }}
          placeholder="For example: I worked as a cook in Helsinki for a year on a work permit. I was laid off last Friday."
          className="w-full rounded-2xl border border-ink/25 bg-card p-5 text-lg shadow-sm outline-none placeholder:text-ink-soft/80 focus:border-ink" />
        <div className="flex flex-wrap items-center gap-4">
          <Button type="submit" disabled={busy || !text.trim()} className="text-lg">Show my steps</Button>
          <span className="text-sm text-ink-soft">No account. Stays in this browser. Never asks for permit or passport numbers.</span>
        </div>
      </form>
      {saved.length > 0 && (
        <section aria-labelledby="saved-title" className="space-y-3 border-t border-rule pt-6">
          <h2 id="saved-title" className="font-serif text-2xl font-semibold">Your saved steps</h2>
          <ul className="space-y-2">
            {saved.map((r) => (
              <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rule bg-card px-4 py-3">
                <span>
                  <span className="font-bold">{r.title}</span>
                  {!!r.summary?.length && (
                    <span className="mt-1 flex flex-wrap gap-1.5">
                      {r.summary.map((t) => <span key={t} className="rounded-full border border-ink/15 bg-paper px-2.5 py-0.5 text-sm">{t}</span>)}
                    </span>
                  )}
                  <span className="mt-1 block text-sm text-ink-soft">Saved {new Date(r.savedAt).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}</span>
                </span>
                <span className="flex gap-2">
                  <Button variant="chip" onClick={() => onOpen?.(r.id)}>Open</Button>
                  <Button variant="quiet" onClick={() => onDelete?.(r.id)} aria-label={`Delete ${r.title}`}>Delete</Button>
                </span>
              </li>
            ))}
          </ul>
          <p className="text-sm text-ink-soft">Saved only in this browser. Delete them any time.</p>
        </section>
      )}
    </section>
  );
}
