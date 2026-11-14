"use client";

import { useState } from "react";
import type { Deadline, Option, Question, Referral, Source, Step } from "@/lib/api";

export function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-calm-100">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-calm-500">{title}</h2>
      {children}
    </section>
  );
}

export function SourceChip({ source }: { source: Source }) {
  let host = source.url;
  try {
    host = new URL(source.url).hostname.replace(/^www\./, "");
  } catch {}
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noreferrer"
      title={source.title}
      className="inline-flex items-center gap-1 rounded-full bg-calm-100 px-2.5 py-0.5 text-xs text-calm-700 hover:bg-calm-500 hover:text-white"
    >
      ↗ {host}
    </a>
  );
}

export function QuestionChips({
  q,
  onAnswer,
}: {
  q: Question;
  onAnswer: (value: Option["value"]) => void;
}) {
  return (
    <div className="space-y-2">
      <p className="font-medium">{q.question}</p>
      <div className="flex flex-wrap gap-2">
        {q.options.map((o) => (
          <button
            key={String(o.value)}
            onClick={() => onAnswer(o.value)}
            className="rounded-full border border-calm-500 px-4 py-1.5 text-sm text-calm-700 hover:bg-calm-500 hover:text-white"
          >
            {o.label}
          </button>
        ))}
        {q.kind === "date" && (
          <input
            type="date"
            aria-label="Pick a date"
            onChange={(e) => e.target.value && onAnswer(e.target.value)}
            className="rounded-full border border-calm-100 px-3 py-1 text-sm"
          />
        )}
      </div>
    </div>
  );
}

function formatDate(iso: string) {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export function DeadlineCard({ d }: { d: Deadline }) {
  return (
    <Card title="Your deadline">
      {d.status === "ok" && d.deadline ? (
        <>
          <p className="text-3xl font-semibold">{formatDate(d.deadline)}</p>
          <p className="mt-1 text-calm-700">
            {d.days_left! >= 0
              ? `${d.days_left} days from today. That's enough time to do this calmly.`
              : "This date has passed. Contact Migri today — there may still be options."}
          </p>
        </>
      ) : (
        <p className="text-xl font-medium">
          {d.status === "not_applicable" ? "No permit deadline for you." : "We need a bit more to work this out."}
        </p>
      )}
      <p className="mt-3 text-sm text-calm-700">{d.reason}</p>
      <div className="mt-3 flex items-center gap-2">
        <SourceChip source={d.source} />
        <span className="text-xs text-calm-500">Not legal advice — confirm with Migri.</span>
      </div>
    </Card>
  );
}

export function ThisWeekCard({ steps }: { steps: Step[] }) {
  return (
    <Card title="This week: 3 things">
      <ol className="space-y-4">
        {steps.map((s, i) => (
          <li key={i} className="flex gap-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-calm-500 text-sm font-semibold text-white">
              {i + 1}
            </span>
            <div>
              <p className="font-medium">{s.title}</p>
              <p className="text-sm text-calm-700">{s.detail}</p>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {s.sources.map((src) => (
                  <SourceChip key={src.url} source={src} />
                ))}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}

function ReferralItem({ r }: { r: Referral }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  return (
    <li className="border-t border-calm-100 pt-3 first:border-0 first:pt-0">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium">{r.name}</p>
          <p className="text-sm text-calm-700">
            {r.role} · {r.organization}
          </p>
          <p className="mt-1 text-sm">{r.why}</p>
          <div className="mt-1.5">
            <SourceChip source={r.source} />
          </div>
        </div>
        <button onClick={() => setOpen(!open)} className="shrink-0 text-sm text-calm-500 underline">
          {open ? "Hide message" : "See message"}
        </button>
      </div>
      {open && (
        <div className="mt-3 rounded-xl bg-calm-50 p-3">
          <pre className="whitespace-pre-wrap font-sans text-sm">{r.message}</pre>
          <button
            onClick={async () => {
              await navigator.clipboard.writeText(r.message);
              setCopied(true);
            }}
            className="mt-2 text-sm text-calm-500 underline"
          >
            {copied ? "Copied ✓" : "Copy"}
          </button>
        </div>
      )}
    </li>
  );
}

export function ReferralsCard({ referrals }: { referrals: Referral[] }) {
  return (
    <Card title="People who can help">
      <ul className="space-y-3">
        {referrals.map((r, i) => (
          <ReferralItem key={i} r={r} />
        ))}
      </ul>
    </Card>
  );
}
