import type { Facts } from "@/lib/api";
import { FIELDS, display } from "@/lib/facts";
import { CheckIcon } from "./icons";
import { cx } from "./primitives";

const REQUIRED = ["citizenship_group", "permit_type", "years_on_work_permit", "job_end_date"] as const;
const OPTIONAL = ["city", "field"] as const;

/** Beside the question: what we know so far. ✓ filled, ○ still needed. */
export function Checklist({ facts }: { facts: Facts }) {
  const row = (id: keyof Facts, optional: boolean) => {
    const f = FIELDS.find((x) => x.id === id)!;
    const value = display(f, facts[id], facts);
    const skipped = facts[id] === "";
    const done = value !== null || skipped;
    return (
      <li key={id} className="flex items-start gap-3 py-2">
        <span aria-hidden className={cx("mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full",
          done ? "bg-verified-soft text-verified" : "border-2 border-dashed border-ink/30")}>
          {done && <CheckIcon className="h-3.5 w-3.5" />}
        </span>
        <span className="min-w-0">
          <span className={cx("block", done ? "font-bold" : "text-ink-soft")}>{f.label}{optional && <span className="font-normal text-ink-soft"> (optional)</span>}</span>
          {value && <span className="block text-sm text-ink-soft">{value}</span>}
          {skipped && <span className="block text-sm text-ink-soft">Skipped</span>}
          <span className="sr-only">{done ? "filled in" : "still needed"}</span>
        </span>
      </li>
    );
  };
  return (
    <aside aria-labelledby="checklist-title" className="rounded-2xl border border-rule bg-card p-5">
      <h2 id="checklist-title" className="font-serif text-xl font-semibold">What we know so far</h2>
      <ul className="mt-2 divide-y divide-rule/70">
        {REQUIRED.map((id) => row(id, false))}
        {OPTIONAL.map((id) => row(id, true))}
      </ul>
    </aside>
  );
}
