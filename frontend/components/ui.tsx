"use client";

import { useState } from "react";
import type { Action, Contact, Deadline, Draft, Option, PlanBOption, Question, ReferralResponse, Source, TimelineStep } from "@/lib/api";

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
      {d.status === "ok" && d.deadline_date ? (
        <>
          <p className="text-3xl font-semibold">{formatDate(d.deadline_date)}</p>
          <p className="mt-1 text-calm-700">
            {d.days_left! >= 0
              ? `${d.days_left} days from today. That's enough time to do this calmly.`
              : "This date has passed. Contact Migri today — there may still be options."}
          </p>
        </>
      ) : d.status === "unclear" && d.possible_dates.length > 0 ? (
        <ul className="space-y-1">
          {d.possible_dates.map((p) => (
            <li key={p.rule_id} className="text-xl font-medium">
              {p.months} months{p.deadline_date ? ` → ${formatDate(p.deadline_date)}` : ""}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xl font-medium">
          {d.status === "not_applicable"
            ? "No permit deadline for you."
            : d.warning
              ? `${d.months ?? "A few"} months from your last day of work.`
              : "We need a bit more to work this out."}
        </p>
      )}
      <p className="mt-3 text-sm text-calm-700">{d.explanation}</p>
      <div className="mt-3 flex items-center gap-2">
        <SourceChip source={d.source} />
        <span className="text-xs text-calm-500">Not legal advice — confirm with Migri.</span>
      </div>
      {d.warning ? (
        <p className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
          {d.warning}{" "}
          <a className="underline" href={d.warning_link ?? d.source.url} target="_blank" rel="noreferrer">
            Check Migri
          </a>
        </p>
      ) : d.verified ? (
        <a href="/how-we-know" className="mt-3 inline-flex rounded-full bg-calm-50 px-3 py-1 text-sm text-calm-700 underline">
          ✓ Checked against Migri today · How we know this
        </a>
      ) : null}
    </Card>
  );
}

function Sources({ sources }: { sources: Source[] }) {
  return (
    <div className="mt-1.5 flex flex-wrap gap-1.5">
      {sources.map((src) => (
        <SourceChip key={src.url} source={src} />
      ))}
    </div>
  );
}

export function ThisWeekCard({ actions }: { actions: Action[] }) {
  return (
    <Card title="This week: 3 things">
      <ol className="space-y-4">
        {actions.map((a, i) => (
          <li key={i} className="flex gap-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-calm-500 text-sm font-semibold text-white">
              {i + 1}
            </span>
            <div>
              <p className="font-medium">{a.title}</p>
              <p className="text-sm text-calm-700">{a.why}</p>
              <ul className="mt-1 list-disc pl-5 text-sm text-calm-700">
                {a.how.map((h, j) => (
                  <li key={j}>{h}</li>
                ))}
              </ul>
              <Sources sources={a.sources} />
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}

export function TimelineCard({ weeks }: { weeks: TimelineStep[] }) {
  return (
    <Card title="Your timeline">
      <ol className="space-y-3">
        {weeks.map((w, i) => (
          <li key={i}>
            <p className="font-medium">{w.week}</p>
            <ul className="list-disc pl-5 text-sm text-calm-700">
              {w.steps.map((s, j) => (
                <li key={j}>{s}</li>
              ))}
            </ul>
            <Sources sources={w.sources} />
          </li>
        ))}
      </ol>
    </Card>
  );
}

export function PlanBCard({ options }: { options: PlanBOption[] }) {
  return (
    <Card title="Plan B">
      <ul className="space-y-3">
        {options.map((o, i) => (
          <li key={i}>
            <p className="font-medium">{o.option}</p>
            <p className="text-sm text-calm-700">{o.why}</p>
            {o.latest_start_date && (
              <p className="text-sm text-calm-700">Start by {formatDate(o.latest_start_date)}</p>
            )}
            <Sources sources={o.sources} />
          </li>
        ))}
      </ul>
    </Card>
  );
}

function ContactItem({ c, draft }: { c: Contact; draft?: Draft }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  return (
    <li className="border-t border-calm-100 pt-3 first:border-0 first:pt-0">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium">{c.name}</p>
          <p className="text-sm text-calm-700">
            {c.role} · {c.company}
          </p>
          <p className="mt-1 text-sm">{c.why_this_person}</p>
          <div className="mt-1.5">
            <SourceChip source={{ title: c.name, url: c.profile_url }} />
          </div>
        </div>
        {draft && (
          <button onClick={() => setOpen(!open)} className="shrink-0 text-sm text-calm-500 underline">
            {open ? "Hide draft" : "See draft"}
          </button>
        )}
      </div>
      {open && draft && (
        <div className="mt-3 rounded-xl bg-calm-50 p-3">
          <pre className="whitespace-pre-wrap font-sans text-sm">{draft.message}</pre>
          <button
            onClick={async () => {
              await navigator.clipboard.writeText(draft.message);
              setCopied(true);
            }}
            className="mt-2 text-sm text-calm-500 underline"
          >
            {copied ? "Copied ✓" : "Copy"}
          </button>
          <p className="mt-1 text-xs text-calm-500">Draft only. Nothing is sent for you.</p>
        </div>
      )}
    </li>
  );
}

const COMMUNITY_LABEL = { professional_group: "Group", event: "Event", union: "Union" } as const;

export function ReferralsCard({ r }: { r: ReferralResponse }) {
  return (
    <>
      {r.companies.length > 0 && (
        <Card title="Companies hiring">
          <ul className="space-y-3">
            {r.companies.map((c, i) => (
              <li key={i}>
                <p className="font-medium">{c.name}</p>
                <p className="text-sm text-calm-700">{c.why_relevant}</p>
                <div className="mt-1.5">
                  <SourceChip source={c.source} />
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {r.contacts.length > 0 && (
        <Card title="People who can help">
          <ul className="space-y-3">
            {r.contacts.map((c, i) => (
              <ContactItem key={i} c={c} draft={r.drafts.find((d) => d.profile_url === c.profile_url)} />
            ))}
          </ul>
        </Card>
      )}
      {r.communities.length > 0 && (
        <Card title="Communities and help">
          <ul className="space-y-2">
            {r.communities.map((g, i) => (
              <li key={i} className="flex flex-wrap items-center gap-2 text-sm">
                <span className="rounded-full bg-calm-50 px-2 py-0.5 text-xs text-calm-700">{COMMUNITY_LABEL[g.type]}</span>
                <a href={g.url} target="_blank" rel="noreferrer" className="underline">
                  {g.name}
                </a>
                {g.date_if_event && <span className="text-calm-500">{formatDate(g.date_if_event)}</span>}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}
