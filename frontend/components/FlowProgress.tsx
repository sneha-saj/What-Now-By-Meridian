import { cx } from "./primitives";

export type Phase = "tell" | "finding" | "roadmap" | "ask";
const PHASES: { id: Phase; label: string }[] = [
  { id: "tell", label: "Tell us" },
  { id: "finding", label: "Finding facts" },
  { id: "roadmap", label: "Your roadmap" },
  { id: "ask", label: "Ask" },
];

/** Row 1: where you are in the flow. Roadmap and Ask are clickable once the roadmap exists. */
export function FlowProgress({ phase, built, onGo }: { phase: Phase; built: boolean; onGo: (p: "roadmap" | "ask") => void }) {
  const at = PHASES.findIndex((p) => p.id === phase);
  return (
    <nav aria-label="Progress">
      <ol className="grid grid-cols-4 gap-2">
        {PHASES.map((p, i) => {
          const state = i < at || (built && i < 2) ? "done" : i === at ? "current" : "todo";
          const clickable = built && (p.id === "roadmap" || p.id === "ask");
          const inner = (
            <>
              <span className={cx("block h-1.5 rounded-full", state === "todo" ? "bg-rule" : state === "current" ? "bg-ink" : "bg-accent")} />
              <span className={cx("mt-2 block text-sm sm:text-base", state === "current" ? "font-bold" : state === "todo" ? "text-ink-soft" : "")}>
                {p.label}
              </span>
            </>
          );
          return (
            <li key={p.id} aria-current={state === "current" ? "step" : undefined}>
              {clickable ? (
                <button onClick={() => onGo(p.id as "roadmap" | "ask")} className="block w-full rounded-lg text-left hover:opacity-80">{inner}</button>
              ) : inner}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
