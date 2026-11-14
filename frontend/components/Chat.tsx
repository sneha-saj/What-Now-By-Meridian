"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatMessage, Option, ProgressStage, Question } from "@/lib/api";
import { Button, cx } from "./primitives";

/** Calm, document-like messages: not bubbles. New assistant text is announced to screen readers. */
export function Thread({ messages }: { messages: ChatMessage[] }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }), [messages.length]);
  return (
    <ol aria-live="polite" aria-relevant="additions" className="space-y-5">
      {messages.map((m, i) =>
        m.role === "assistant" ? (
          <li key={i} className="animate-fade-up border-l-[3px] border-accent pl-4">
            <p className="text-sm font-bold text-ink-soft">What Now?</p>
            <p className="mt-0.5 text-lg">{m.text}</p>
          </li>
        ) : (
          <li key={i} className="animate-fade-up ml-auto max-w-[85%] rounded-xl bg-paper-deep px-4 py-3">
            <p className="sr-only">You said:</p>
            <p>{m.text}</p>
          </li>
        ),
      )}
      <div ref={end} />
    </ol>
  );
}

/** Tap-to-answer options for the current question, plus the date picker for date questions. */
export function QuickReplies({
  question, disabled, onAnswer,
}: { question: Question; disabled?: boolean; onAnswer: (value: string, label: string) => void }) {
  const [date, setDate] = useState("");
  return (
    <fieldset className="space-y-3" disabled={disabled}>
      <legend className="sr-only">{question.question}</legend>
      <div className="flex flex-wrap gap-2">
        {question.options.map((o: Option) => (
          <Button key={o.value} variant="chip" onClick={() => onAnswer(o.value, o.label)}>
            {o.label}
          </Button>
        ))}
      </div>
      {question.kind === "date" && (
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (date) onAnswer(date, date);
          }}
        >
          <label htmlFor="pick-date" className="text-ink-soft">Or pick the date:</label>
          <input id="pick-date" type="date" value={date} onChange={(e) => setDate(e.target.value)}
            className="min-h-11 rounded-lg border border-ink/30 bg-card px-3" />
          <Button type="submit" variant="chip" disabled={!date}>Use this date</Button>
        </form>
      )}
    </fieldset>
  );
}

/** Free-text box. Enter sends, Shift+Enter adds a line. */
export function Composer({
  onSend, disabled, placeholder, label = "Your message",
}: { onSend: (text: string) => void; disabled?: boolean; placeholder?: string; label?: string }) {
  const [text, setText] = useState("");
  function send() {
    if (!text.trim() || disabled) return;
    onSend(text.trim());
    setText("");
  }
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        send();
      }}
      className="space-y-3"
    >
      <label htmlFor="composer" className="sr-only">{label}</label>
      <textarea
        id="composer"
        value={text}
        rows={3}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send();
          }
        }}
        placeholder={placeholder}
        className="w-full resize-y rounded-2xl border border-ink/25 bg-card p-4 text-lg shadow-sm outline-none placeholder:text-ink-soft/80 focus:border-ink"
      />
      <Button type="submit" disabled={disabled || !text.trim()}>Continue</Button>
    </form>
  );
}

const STAGE_LABEL: Record<ProgressStage, string> = {
  reading_situation: "Reading your situation",
  checking_rules: "Checking Migri's rules",
  finding_steps: "Finding your next steps",
  finding_people: "Looking for people who can refer you",
};

/** Lines that tick off one by one while the backend works. */
export function ProgressLines({ expected, reached }: { expected: ProgressStage[]; reached: ProgressStage[] }) {
  const current = reached[reached.length - 1];
  const stages = [...reached, ...expected.filter((s) => !reached.includes(s))];
  return (
    <div role="status" aria-live="polite" className="animate-fade-up rounded-2xl border border-rule bg-card p-5">
      <ul className="space-y-2">
        {stages.map((s) => {
          const done = reached.includes(s) && s !== current;
          const active = s === current || (!current && s === stages[0]);
          return (
            <li key={s} className={cx("flex items-center gap-3", !done && !active && "text-ink-soft")}>
              <span aria-hidden className={cx(
                "flex h-6 w-6 items-center justify-center rounded-full text-sm",
                done && "bg-verified-soft text-verified",
                active && "border-2 border-accent motion-safe:animate-pulse",
                !done && !active && "border border-rule",
              )}>
                {done ? "✓" : ""}
              </span>
              <span className={cx(active && "font-bold")}>{STAGE_LABEL[s]}</span>
              <span className="sr-only">{done ? "done" : active ? "in progress" : "waiting"}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
