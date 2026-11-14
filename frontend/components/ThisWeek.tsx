import type { Action, PlanResponse } from "@/lib/api";
import { Sources, cx, formatDate } from "./primitives";

function ActionCard({ a, i, done, onToggle }: { a: Action; i: number; done: boolean; onToggle: () => void }) {
  const id = `action-${i}`;
  return (
    <li className={cx("animate-fade-up rounded-2xl border bg-card p-5 shadow-[0_2px_12px_rgba(28,42,69,0.05)] sm:p-6",
      done ? "border-verified/40" : "border-rule")} style={{ animationDelay: `${i * 90}ms` }}>
      <div className="flex items-start gap-4">
        <input id={id} type="checkbox" checked={done} onChange={onToggle}
          className="mt-1.5 h-6 w-6 shrink-0 cursor-pointer accent-[var(--color-verified)]" />
        <div className="min-w-0">
          <label htmlFor={id} className={cx("cursor-pointer font-serif text-xl font-semibold", done && "text-ink-soft line-through decoration-1")}>
            {a.title}
          </label>
          <p className="mt-1 text-ink-soft">{a.why}</p>
          {a.how.length > 0 && (
            <ol className="mt-3 list-decimal space-y-1 pl-5">
              {a.how.map((h, j) => <li key={j}>{h}</li>)}
            </ol>
          )}
          <Sources sources={a.sources} />
        </div>
      </div>
    </li>
  );
}

/** Step 3: exactly 3 cards. Timeline and Plan B are folded away under "See the full plan". */
export function ThisWeek({
  plan, done, onToggle,
}: { plan: PlanResponse; done: Record<number, boolean>; onToggle: (i: number) => void }) {
  const count = plan.this_week.filter((_, i) => done[i]).length;
  return (
    <section aria-labelledby="week-title" className="space-y-6">
      <div>
        <h2 id="week-title" className="font-serif text-4xl font-semibold">This week</h2>
        <p className="mt-2 text-lg text-ink-soft">
          Three things, in this order. {count > 0 ? `${count} of 3 done. Well done.` : "Tick them off as you go."}
        </p>
      </div>
      <ol className="space-y-4">
        {plan.this_week.map((a, i) => (
          <ActionCard key={i} a={a} i={i} done={!!done[i]} onToggle={() => onToggle(i)} />
        ))}
      </ol>

      <details className="group rounded-2xl border border-rule bg-card">
        <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 px-5 py-3 font-bold sm:px-6">
          See the full plan
          <span aria-hidden className="text-ink-soft transition-transform group-open:rotate-180">⌄</span>
        </summary>
        <div className="space-y-8 border-t border-rule px-5 pb-6 pt-5 sm:px-6">
          {plan.timeline.length > 0 && (
            <div>
              <h3 className="font-serif text-2xl font-semibold">Week by week</h3>
              <ol className="mt-4 space-y-5 border-l-2 border-accent/50 pl-5">
                {plan.timeline.map((w, i) => (
                  <li key={i}>
                    <p className="font-bold">{w.week}</p>
                    <ul className="mt-1 list-disc space-y-1 pl-5">{w.steps.map((s, j) => <li key={j}>{s}</li>)}</ul>
                    <Sources sources={w.sources} />
                  </li>
                ))}
              </ol>
            </div>
          )}
          <div>
            <h3 className="font-serif text-2xl font-semibold">Plan B</h3>
            {plan.plan_b.length > 0 ? (
              <ul className="mt-4 space-y-5">
                {plan.plan_b.map((p) => (
                  <li key={p.id || p.option} className="rounded-xl bg-paper p-4">
                    <p className="font-bold">{p.option}</p>
                    {p.who_it_fits && <p className="mt-1"><span className="text-ink-soft">Who it fits: </span>{p.who_it_fits}</p>}
                    <p className="mt-1">{p.why}</p>
                    {p.latest_start_date && (
                      <p className="mt-1"><span className="text-ink-soft">Start by: </span><strong>{formatDate(p.latest_start_date)}</strong></p>
                    )}
                    <Sources sources={p.sources} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2">{plan.plan_b_note ?? "We couldn't find another option that clearly fits. Check with Migri or your union."}</p>
            )}
          </div>
        </div>
      </details>
      <p className="text-sm text-ink-soft">{plan.disclaimer}</p>
    </section>
  );
}
