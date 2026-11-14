"use client";

import { useState } from "react";
import type { Facts } from "@/lib/api";
import { FIELDS, YES_NO, display, parse, type Field, type FieldDef } from "@/lib/facts";
import { PencilIcon, PersonIcon } from "./icons";
import { Button, cx } from "./primitives";

function Editor({ f, value, onSave, onClose }: { f: FieldDef; value: unknown; onSave: (v: Facts[Field]) => void; onClose: () => void }) {
  const [draft, setDraft] = useState(value === null || value === undefined ? "" : String(value));
  const id = `edit-${f.id}`;
  return (
    <form
      className="animate-fade-up mt-3 flex flex-wrap items-center gap-3 rounded-2xl border border-rule bg-card p-4"
      onSubmit={(e) => { e.preventDefault(); onSave(parse(f, draft)); onClose(); }}
      onKeyDown={(e) => e.key === "Escape" && onClose()}
    >
      <label htmlFor={id} className="font-bold">{f.label}</label>
      {f.kind === "choice" ? (
        <select id={id} value={draft} autoFocus onChange={(e) => setDraft(e.target.value)} className="min-h-11 rounded-xl border border-ink/30 bg-card px-3">
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

/** "Your situation": one line of chips. Person icon = from you; dashed = still missing. Tap to edit.
 *  `open`/`onOpen` let the page open an editor (e.g. "Pick the exact date"). */
export function SituationStrip({
  facts, onEdit, open: openProp, onOpen, showSearchFields = false,
}: {
  facts: Facts;
  onEdit: (field: Field, value: Facts[Field]) => void;
  open?: Field | null;
  onOpen?: (f: Field | null) => void;
  showSearchFields?: boolean;
}) {
  const [openLocal, setOpenLocal] = useState<Field | null>(null);
  const open = openProp !== undefined ? openProp : openLocal;
  const setOpen = onOpen ?? setOpenLocal;
  const chips = FIELDS.filter((f) => f.required || display(f, facts[f.id]) !== null || (showSearchFields && (f.id === "city" || f.id === "field")));
  const editing = FIELDS.find((f) => f.id === open);
  return (
    <section aria-labelledby="situation-title" className="rounded-2xl border border-rule bg-card px-4 py-3">
      <div className="flex items-center gap-3">
      <h2 id="situation-title" className="shrink-0 font-serif text-lg font-semibold">Your situation</h2>
      <ul className="flex min-w-0 flex-1 gap-2 overflow-x-auto py-1 [scrollbar-width:thin]">
        {chips.map((f) => {
          const text = display(f, facts[f.id], facts);
          return (
            <li key={f.id}>
              <button
                onClick={() => setOpen(open === f.id ? null : f.id)}
                aria-expanded={open === f.id}
                className={cx(
                  "group inline-flex min-h-11 items-center gap-2 whitespace-nowrap rounded-full px-4 py-2 transition-colors",
                  text ? "border border-ink/20 bg-card hover:border-ink" : "border-2 border-dashed border-ink/30 text-ink-soft hover:border-ink-soft",
                )}
              >
                {text ? <PersonIcon className="h-4 w-4 text-accent-ink" /> : null}
                <span>{text ?? `${f.label}: missing`}</span>
                <span className="sr-only">{text ? "(from your answers) Edit" : "Add"}</span>
                <PencilIcon className="h-3.5 w-3.5 text-ink-soft opacity-60 group-hover:opacity-100" />
              </button>
            </li>
          );
        })}
      </ul>
      </div>
      {editing && <Editor key={editing.id} f={editing} value={facts[editing.id]} onSave={(v) => onEdit(editing.id, v)} onClose={() => setOpen(null)} />}
    </section>
  );
}
