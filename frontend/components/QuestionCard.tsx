"use client";

import { useState } from "react";
import type { Question } from "@/lib/api";
import { Button, cx } from "./primitives";

/** One question at a time: serif question, tap buttons (incl. "Not sure"), or answer in your own words. */
export function QuestionCard({
  question, busy, onAnswer, onText,
}: {
  question: Question;
  busy?: boolean;
  onAnswer: (value: string) => void;
  onText: (text: string) => void;
}) {
  const [date, setDate] = useState("");
  const [text, setText] = useState("");
  const [picked, setPicked] = useState<string | null>(null);
  const choose = (value: string) => {
    setPicked(value);
    onAnswer(value);
  };
  return (
    <section aria-labelledby="q-title" className="animate-fade-up rounded-3xl border border-rule bg-card p-6 shadow-[0_6px_24px_rgba(28,42,69,0.06)] sm:p-8">
      <p className="text-sm text-ink-soft">One quick question</p>
      <h2 id="q-title" className="mt-1 font-serif text-3xl font-semibold leading-snug sm:text-4xl">{question.question}</h2>
      <fieldset disabled={busy || picked !== null} className="mt-6 space-y-5">
        <legend className="sr-only">Choose an answer</legend>
        <div className="flex flex-wrap gap-3">
          {question.options.map((o) => (
            <Button key={o.value} variant="chip" aria-pressed={picked === o.value}
              className={cx("text-lg", picked === o.value && "!border-ink !bg-ink !text-paper !opacity-100")}
              onClick={() => choose(o.value)}>
              {picked === o.value && <span aria-hidden>✓</span>}
              {o.label}
            </Button>
          ))}
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

/** First screen: the warm opening line and one text box. */
export function Welcome({ busy, onSubmit }: { busy?: boolean; onSubmit: (text: string) => void }) {
  const [text, setText] = useState("");
  return (
    <section aria-labelledby="welcome-title" className="animate-fade-up mx-auto max-w-3xl space-y-6 py-6 sm:py-12">
      <h1 id="welcome-title" className="font-serif text-4xl font-semibold leading-tight sm:text-6xl">
        I&apos;m sorry this happened. Let&apos;s figure out what&apos;s next, together.
      </h1>
      <p className="text-xl text-ink-soft">
        Tell me in a sentence or two what happened. I&apos;ll ask only what&apos;s missing, then build your roadmap from
        official Finnish sources, found live.
      </p>
      <form onSubmit={(e) => { e.preventDefault(); if (text.trim()) onSubmit(text.trim()); }} className="space-y-4">
        <label htmlFor="welcome-text" className="sr-only">What happened?</label>
        <textarea id="welcome-text" rows={4} value={text} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (text.trim()) onSubmit(text.trim()); } }}
          placeholder="For example: I worked as a cook in Helsinki for a year on a work permit. I was laid off last Friday."
          className="w-full rounded-2xl border border-ink/25 bg-card p-5 text-lg shadow-sm outline-none placeholder:text-ink-soft/80 focus:border-ink" />
        <div className="flex flex-wrap items-center gap-4">
          <Button type="submit" disabled={busy || !text.trim()} className="text-lg">Build my roadmap</Button>
          <span className="text-sm text-ink-soft">No account. Stays in this browser tab. Never asks for permit or passport numbers.</span>
        </div>
      </form>
    </section>
  );
}
