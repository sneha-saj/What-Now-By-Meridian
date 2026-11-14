"use client";

import { useState } from "react";
import type { Facts } from "@/lib/api";
import { DEFAULT_PERSONAL, FIELDS, YES_NO, display, parse, type Field, type FieldDef } from "@/lib/facts";
import { CheckIcon, PencilIcon } from "./icons";
import { Button, cx } from "./primitives";

const REQUIRED: Field[] = ["lost_job", "citizenship_group", "permit_type", "years_on_work_permit", "job_end_date"];

function Editor({ f, value, onSave, onClose }: { f: FieldDef; value: unknown; onSave: (v: Facts[Field]) => void; onClose: () => void }) {
  const [draft, setDraft] = useState(value === null || value === undefined ? "" : String(value));
  const id = `edit-${f.id}`;
  return (
    <form
      className="animate-fade-up mt-2 flex flex-wrap items-center gap-2 rounded-xl border border-rule bg-paper p-3"
      onSubmit={(e) => { e.preventDefault(); onSave(parse(f, draft)); onClose(); }}
      onKeyDown={(e) => e.key === "Escape" && onClose()}
    >
      <label htmlFor={id} className="sr-only">{f.label}</label>
      {f.kind === "choice" ? (
        <select id={id} value={draft} autoFocus onChange={(e) => setDraft(e.target.value)} className="min-h-11 min-w-0 max-w-full rounded-xl border border-ink/30 bg-card px-3">
          <option value="">Not known</option>
          {(f.choices === YES_NO ? YES_NO : f.choices!).map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
      ) : (
        <input id={id} type={f.kind === "date" ? "date" : "text"} value={draft} autoFocus onChange={(e) => setDraft(e.target.value)}
          className="min-h-11 min-w-0 flex-1 rounded-xl border border-ink/30 bg-card px-3" />
      )}
      <Button type="submit">Save</Button>
      <Button type="button" variant="quiet" onClick={onClose}>Cancel</Button>
    </form>
  );
}

/** "What we know so far": the one place for the person's facts. ✓ filled, dashed = still needed; every row can be
 *  edited. Beside the questions it's a column; under the roadmap (`wide`) it spreads into a grid.
 *  `open`/`onOpen` let the page open an editor (e.g. "Pick the exact date", "Add city"). */
export function Checklist({
  facts, onEdit, open: openProp, onOpen, wide = false, also = [],
}: {
  facts: Facts;
  onEdit: (field: Field, value: Facts[Field]) => void;
  open?: Field | null;
  onOpen?: (f: Field | null) => void;
  wide?: boolean;
  also?: Field[]; // extra rows to show even when empty (e.g. city on the Opportunities tab)
}) {
  const [openLocal, setOpenLocal] = useState<Field | null>(null);
  const open = openProp !== undefined ? openProp : openLocal;
  const setOpen = onOpen ?? setOpenLocal;

  // The deadline facts, the personal questions chosen for this person, then anything else we happen to know.
  const personal = ((facts.to_ask ?? DEFAULT_PERSONAL) as Field[]).filter((id) => FIELDS.some((x) => x.id === id));
  const known = FIELDS.filter((f) => display(f, facts[f.id], facts) !== null).map((f) => f.id);
  // "Time on a work permit" only matters for a work-based permit (or while the permit is still unknown).
  const permit = facts.permit_type;
  const required = REQUIRED.filter((id) => id !== "years_on_work_permit" || !permit || permit === "work_based" || permit === "not_sure"
    || facts.years_on_work_permit !== undefined && facts.years_on_work_permit !== null);
  const ids = [...new Set<Field>([...required, ...personal, ...also, ...known])];

  const row = (id: Field) => {
    const f = FIELDS.find((x) => x.id === id)!;
    const value = display(f, facts[id], facts);
    const skipped = facts[id] === "";
    const done = value !== null || skipped;
    const forSteps = !REQUIRED.includes(id) && personal.includes(id);
    return (
      <li key={id} className="py-2">
        <div className="flex items-start gap-3">
          <span aria-hidden className={cx("mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full",
            done ? "bg-verified-soft text-verified" : "border-2 border-dashed border-ink/30")}>
            {done && <CheckIcon className="h-3.5 w-3.5" />}
          </span>
          <span className="min-w-0 flex-1">
            <span className={cx("block", done ? "font-bold" : "text-ink-soft")}>
              {f.label}{forSteps && <span className="font-normal text-ink-soft"> · for your steps</span>}
            </span>
            {value && <span className="block text-sm text-ink-soft">{value}</span>}
            {skipped && <span className="block text-sm text-ink-soft">Skipped</span>}
            <span className="sr-only">{done ? "filled in" : "still needed"}</span>
          </span>
          <button onClick={() => setOpen(open === id ? null : id)} aria-expanded={open === id}
            className="inline-flex min-h-9 shrink-0 items-center gap-1 rounded-full px-2.5 text-sm text-ink-soft hover:bg-paper-deep hover:text-ink">
            <PencilIcon /> {done ? "Edit" : "Add"}<span className="sr-only"> {f.label}</span>
          </button>
        </div>
        {open === id && <Editor key={id} f={f} value={facts[id]} onSave={(v) => onEdit(id, v)} onClose={() => setOpen(null)} />}
      </li>
    );
  };

  return (
    <aside aria-labelledby="checklist-title" className="rounded-2xl border border-rule bg-card p-5">
      <h2 id="checklist-title" className="font-serif text-xl font-semibold">What we know so far</h2>
      <p className="mt-1 text-sm text-ink-soft">Something wrong? Edit it here and everything updates.</p>
      <ul className={cx("mt-2", wide ? "grid gap-x-8 sm:grid-cols-2 lg:grid-cols-3" : "divide-y divide-rule/70")}>
        {ids.map(row)}
      </ul>
    </aside>
  );
}
