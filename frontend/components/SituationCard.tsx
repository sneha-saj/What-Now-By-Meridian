"use client";

import { useState } from "react";
import type { Facts } from "@/lib/api";
import { cx, formatDate } from "./primitives";

type Field = keyof Facts;
type Choice = { value: string; label: string };

const YES_NO: Choice[] = [{ value: "true", label: "Yes" }, { value: "false", label: "No" }];

/** The fields shown on the card, in order. `required` ones are what the deadline needs. */
const FIELDS: { id: Field; label: string; required?: boolean; kind: "choice" | "date" | "text"; choices?: Choice[] }[] = [
  { id: "citizenship_group", label: "Citizenship", required: true, kind: "choice", choices: [
    { value: "eu_eea", label: "EU / EEA citizen" }, { value: "other", label: "Outside the EU / EEA" }, { value: "unknown", label: "Not sure" }] },
  { id: "citizenship_country", label: "Country", kind: "text" },
  { id: "permit_type", label: "Residence permit", required: true, kind: "choice", choices: [
    { value: "work_based", label: "Work-based" }, { value: "specialist_blue_card", label: "Specialist / EU Blue Card" },
    { value: "student", label: "Student" }, { value: "family_based", label: "Family-based" },
    { value: "permanent", label: "Permanent" }, { value: "not_sure", label: "Not sure" }] },
  { id: "years_on_work_permit", label: "Time on a work permit", required: true, kind: "choice", choices: [
    { value: "under_2", label: "2 years or less" }, { value: "over_2", label: "More than 2 years" }, { value: "not_sure", label: "Not sure" }] },
  { id: "job_end_date", label: "Last day of work", required: true, kind: "date" },
  { id: "city", label: "City", kind: "text" },
  { id: "field", label: "Work", kind: "text" },
  { id: "studied_in_finland", label: "Studied in Finland", kind: "choice", choices: YES_NO },
  { id: "family_in_finland", label: "Family in Finland", kind: "choice", choices: YES_NO },
];

function display(f: (typeof FIELDS)[number], value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (f.id === "years_on_work_permit" && typeof value === "number") return `${value} ${value === 1 ? "year" : "years"}`;
  if (f.kind === "date") return formatDate(String(value));
  if (f.choices) return f.choices.find((c) => c.value === String(value))?.label ?? String(value);
  return String(value);
}

function parse(f: (typeof FIELDS)[number], raw: string): Facts[Field] {
  if (raw === "") return null;
  if (f.choices === YES_NO) return raw === "true";
  return raw as Facts[Field];
}

function FieldRow({
  f, value, confirmed, onSave,
}: { f: (typeof FIELDS)[number]; value: unknown; confirmed: boolean; onSave: (v: Facts[Field]) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const shown = display(f, value);
  const inputId = `edit-${f.id}`;

  function start() {
    setDraft(value === null || value === undefined ? "" : String(value));
    setEditing(true);
  }

  return (
    <div className="border-b border-dashed border-rule py-3 last:border-0">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <dt className="text-sm text-ink-soft">{f.label}</dt>
          <dd className="mt-0.5 flex items-center gap-2">
            {shown ? (
              confirmed ? (
                <>
                  <span aria-hidden className="text-verified">✓</span>
                  <span>{shown}</span>
                  <span className="sr-only">(confirmed)</span>
                </>
              ) : (
                <>
                  <span aria-hidden className="h-2 w-2 shrink-0 rounded-full border border-dashed border-ink-soft" />
                  <span className="underline decoration-ink-soft decoration-dotted underline-offset-4">{shown}</span>
                  <span className="sr-only">(our guess from your message, please check)</span>
                </>
              )
            ) : (
              <span className="text-ink-soft italic">{f.required ? "We'll ask" : "Not given"}</span>
            )}
          </dd>
        </div>
        {!editing && (
          <button
            onClick={start}
            className="flex min-h-11 min-w-11 items-center justify-center rounded-lg text-ink-soft hover:bg-paper-deep hover:text-ink"
            aria-label={`Edit ${f.label}`}
          >
            <span aria-hidden>✎</span>
          </button>
        )}
      </div>
      {editing && (
        <form
          className="mt-2 flex flex-wrap items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            onSave(parse(f, draft));
            setEditing(false);
          }}
        >
          <label htmlFor={inputId} className="sr-only">{f.label}</label>
          {f.kind === "choice" ? (
            <select id={inputId} value={draft} onChange={(e) => setDraft(e.target.value)}
              className="min-h-11 rounded-lg border border-ink/30 bg-card px-3">
              <option value="">Not known</option>
              {f.choices!.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          ) : (
            <input id={inputId} type={f.kind === "date" ? "date" : "text"} value={draft} autoFocus
              onChange={(e) => setDraft(e.target.value)}
              className="min-h-11 min-w-0 flex-1 rounded-lg border border-ink/30 bg-card px-3" />
          )}
          <button type="submit" className="min-h-11 rounded-lg bg-ink px-4 font-bold text-paper">Save</button>
          <button type="button" onClick={() => setEditing(false)} className="min-h-11 px-2 text-ink-soft underline">Cancel</button>
        </form>
      )}
    </div>
  );
}

export function SituationCard({
  facts, confirmed, onEdit,
}: { facts: Facts; confirmed: Field[]; onEdit: (field: Field, value: Facts[Field]) => void }) {
  const rows = FIELDS.filter((f) => f.required || display(f, facts[f.id]) !== null);
  return (
    <section aria-labelledby="situation-title" className="rounded-2xl border border-rule bg-card p-5 sm:p-6">
      <h2 id="situation-title" className="font-serif text-xl font-semibold">Your situation</h2>
      <p className="mt-1 text-sm text-ink-soft">
        <span aria-hidden className="text-verified">✓</span> confirmed by you ·{" "}
        <span className="underline decoration-dotted underline-offset-4">dotted</span> = our guess. Tap ✎ to correct anything.
      </p>
      <dl className={cx("mt-3")}>
        {rows.map((f) => (
          <FieldRow key={f.id} f={f} value={facts[f.id]} confirmed={confirmed.includes(f.id)}
            onSave={(v) => onEdit(f.id, v)} />
        ))}
      </dl>
      <p className="mt-4 text-xs text-ink-soft">Stays in this browser tab only. We never ask for permit or passport numbers.</p>
    </section>
  );
}
