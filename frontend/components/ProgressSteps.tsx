import { STEPS, type Step } from "@/lib/api";
import { cx } from "./primitives";

export function ProgressSteps({ current }: { current: Step | null }) {
  const at = current ? STEPS.findIndex((s) => s.id === current) : 0;
  return (
    <nav aria-label="Progress">
      <ol className="flex flex-wrap gap-x-6 gap-y-2">
        {STEPS.map((s, i) => {
          const state = i < at ? "done" : i === at ? "current" : "todo";
          return (
            <li key={s.id} aria-current={state === "current" ? "step" : undefined} className="flex items-center gap-2">
              <span
                aria-hidden
                className={cx(
                  "flex h-6 w-6 items-center justify-center rounded-full border text-xs font-bold",
                  state === "done" && "border-accent bg-accent text-ink",
                  state === "current" && "border-ink bg-ink text-paper",
                  state === "todo" && "border-rule text-ink-soft",
                )}
              >
                {state === "done" ? "✓" : i + 1}
              </span>
              <span className={cx("text-[0.95rem]", state === "todo" ? "text-ink-soft" : "font-bold")}>
                {s.label}
                <span className="sr-only">{state === "done" ? " (done)" : state === "current" ? " (current step)" : ""}</span>
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
