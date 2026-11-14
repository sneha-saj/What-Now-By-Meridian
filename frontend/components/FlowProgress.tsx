import { cx } from "./primitives";

export type Phase = "tell" | "finding" | "roadmap";
const PHASES: { id: Phase; label: string }[] = [
  { id: "tell", label: "Tell us" },
  { id: "finding", label: "Finding facts" },
  { id: "roadmap", label: "Your roadmap" },
];

/** Shown only while the roadmap is being set up. Once it's built, the page switches to tabs. */
export function FlowProgress({ phase }: { phase: Phase }) {
  const at = PHASES.findIndex((p) => p.id === phase);
  return (
    <nav aria-label="Progress" className="min-w-0 flex-1">
      <ol className="grid grid-cols-3 gap-2">
        {PHASES.map((p, i) => {
          const state = i < at ? "done" : i === at ? "current" : "todo";
          return (
            <li key={p.id} aria-current={state === "current" ? "step" : undefined}>
              <span className={cx("block h-1.5 rounded-full", state === "todo" ? "bg-rule" : state === "current" ? "bg-ink" : "bg-accent")} />
              <span className={cx("mt-2 block text-sm sm:text-base", state === "current" ? "font-bold" : state === "todo" ? "text-ink-soft" : "")}>
                {p.label}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
