import type { Deadline } from "@/lib/api";
import { GentleWarning, SourceChip, VerifiedBadge, cx, formatDate } from "./primitives";

/**
 * The meridian line: Today → Your deadline, with week markers.
 * This week's actions hang from week 1; finished ones are filled dots. It draws in once.
 */
export function MeridianLine({
  daysLeft, deadlineDate, actions = 0, done = {}, compact = false,
}: { daysLeft: number; deadlineDate: string; actions?: number; done?: Record<number, boolean>; compact?: boolean }) {
  const total = Math.max(daysLeft, 7);
  const weeks = [1, 2, 4, 8].filter((w) => w * 7 < total - 3);
  const pos = (days: number) => `${Math.min(100, (days / total) * 100)}%`;
  const doneCount = Object.values(done).filter(Boolean).length;
  const today = new Date();

  return (
    <figure className={cx("relative", compact ? "pb-14 pt-8" : "pb-20 pt-10")} aria-label={`Timeline from today to ${formatDate(deadlineDate)}`}>
      <div className="relative mx-2 h-px">
        <div className="animate-draw absolute inset-0 h-[2px] rounded bg-accent" />
        {/* Today */}
        <div className="absolute -top-[7px] left-0 -translate-x-1/2">
          <span className="block h-4 w-4 rounded-full border-2 border-accent bg-card" />
        </div>
        <span className="absolute -top-8 left-0 -translate-x-1/4 text-sm font-bold">Today</span>
        {/* Week markers */}
        {weeks.map((w) => (
          <div key={w} className="animate-fade-up absolute -top-[5px] -translate-x-1/2" style={{ left: pos(w * 7), animationDelay: `${300 + w * 60}ms` }}>
            <span className="block h-3 w-px bg-ink-soft" />
            <span className="absolute left-1/2 top-4 -translate-x-1/2 whitespace-nowrap text-xs text-ink-soft">Week {w}</span>
          </div>
        ))}
        {/* This week's actions hang from week 1 */}
        {actions > 0 && (
          <div className="absolute top-0 -translate-x-1/2" style={{ left: pos(5) }} aria-hidden>
            <span className="mx-auto block h-9 w-px bg-rule" />
            <div className="flex gap-1">
              {Array.from({ length: actions }, (_, i) => (
                <span key={i} className={cx("block h-3 w-3 rounded-full border-2 border-accent transition-colors", done[i] ? "bg-accent" : "bg-card")} />
              ))}
            </div>
          </div>
        )}
        {/* Deadline */}
        <div className="absolute -top-[9px] right-0 translate-x-1/2">
          <span className="block h-5 w-5 rounded-full bg-ink" />
        </div>
        <span className="absolute -top-8 right-0 translate-x-1/4 text-right text-sm font-bold">Your deadline</span>
      </div>
      <figcaption className="sr-only">
        {`Today is ${today.toLocaleDateString("en-GB")}. Your deadline is ${formatDate(deadlineDate)}, ${daysLeft} days away.`}
        {actions > 0 && ` ${doneCount} of ${actions} things for this week done.`}
      </figcaption>
    </figure>
  );
}

function CheckNote({ d }: { d: Deadline }) {
  if (d.check_status === "verified") return <VerifiedBadge />;
  if (d.check_status === "mismatch")
    return (
      <GentleWarning>
        {d.warning}{" "}
        <a href={d.warning_link ?? d.source.url} target="_blank" rel="noreferrer" className="font-bold underline">
          Check Migri<span className="sr-only"> (opens in a new tab)</span>
        </a>
      </GentleWarning>
    );
  if (d.check_status === "error")
    return (
      <p className="inline-flex min-h-9 items-center gap-2 rounded-full bg-paper-deep px-3 py-1 text-sm text-ink-soft">
        <span aria-hidden>○</span> Couldn&apos;t check Migri right now.{" "}
        <a href="/how-we-know" className="underline">How we check</a>
      </p>
    );
  return null;
}

function weeksText(days: number) {
  if (days < 0) return "This date has passed. Contact Migri today: there may still be options.";
  if (days < 14) return `That's ${days} ${days === 1 ? "day" : "days"} from now.`;
  return `That's ${Math.round(days / 7)} weeks from now.`;
}

/** Step 2: the hero moment. */
export function DeadlineHero({ d, actions, done }: { d: Deadline; actions?: number; done?: Record<number, boolean> }) {
  const hasDate = d.status === "ok" && d.deadline_date && d.days_left !== null && d.days_left !== undefined;
  return (
    <section aria-labelledby="deadline-title" className="animate-fade-up space-y-6">
      <h2 id="deadline-title" className="text-lg text-ink-soft">Your deadline</h2>

      {hasDate ? (
        <>
          <div>
            <p className="font-serif text-5xl font-semibold leading-tight sm:text-7xl">{formatDate(d.deadline_date!)}</p>
            <p className="mt-3 text-xl">{weeksText(d.days_left!)}</p>
          </div>
          {d.days_left! > 0 && (
            <MeridianLine daysLeft={d.days_left!} deadlineDate={d.deadline_date!} actions={actions} done={done} />
          )}
        </>
      ) : d.status === "unclear" && d.possible_dates.length > 0 ? (
        <div className="space-y-3">
          <p className="font-serif text-3xl font-semibold sm:text-4xl">It depends on one detail</p>
          <ul className="space-y-2">
            {d.possible_dates.map((p) => (
              <li key={p.rule_id} className="text-xl">
                <span className="font-serif font-semibold">{p.months} months</span>
                {p.deadline_date && <> → {formatDate(p.deadline_date)}</>}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="font-serif text-4xl font-semibold leading-tight sm:text-5xl">
          {d.status === "not_applicable" ? "Your permit doesn't depend on this job." : "We need one more detail."}
        </p>
      )}

      <div className="max-w-2xl space-y-4">
        <p className="text-lg">{d.explanation}</p>
        <div className="flex flex-wrap items-center gap-3">
          <SourceChip source={d.source} />
          <CheckNote d={d} />
        </div>
        <p className="text-sm text-ink-soft">Guidance, not legal advice. If anything is unclear, check with Migri or your union.</p>
      </div>
    </section>
  );
}
