"use client";

import { useState } from "react";
import type { LogLine, Who } from "@/lib/activity";
import { GlobeIcon } from "./icons";
import { cx } from "./primitives";

const WHO: Record<Who, { label: string; className: string }> = {
  gemini: { label: "Gemini", className: "text-accent-ink" },
  exa: { label: "Exa", className: "text-verified" },
  code: { label: "Rules", className: "text-ink" },
};

function Mark({ who }: { who: Who }) {
  if (who === "exa") return <GlobeIcon className="h-3.5 w-3.5 text-verified" />;
  if (who === "gemini") return <span aria-hidden className="text-accent-ink">✦</span>;
  return <span aria-hidden className="text-ink">⚙</span>;
}

/** Small grey log of what's happening behind the scenes: who asked, who searched, what was found. */
export function ActivityLog({ lines, busy }: { lines: LogLine[]; busy: boolean }) {
  const [all, setAll] = useState(false);
  if (!lines.length) return null;
  const shown = all ? lines : lines.slice(-8);
  return (
    <section aria-labelledby="activity-title" className="text-sm text-ink-soft">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="activity-title" className="font-bold">What&apos;s happening{busy && <span className="motion-safe:animate-pulse"> …</span>}</h2>
        {lines.length > 8 && (
          <button onClick={() => setAll(!all)} className="min-h-9 underline">{all ? "Show less" : `Show all ${lines.length}`}</button>
        )}
      </div>
      <ol aria-live="polite" className="mt-2 space-y-1.5 border-l border-rule pl-3">
        {shown.map((l) => (
          <li key={l.id} className="animate-fade-up flex gap-2">
            <span className="mt-0.5 shrink-0"><Mark who={l.who} /></span>
            <span>
              <span className={cx("font-bold", WHO[l.who].className)}>{WHO[l.who].label}</span>{" "}
              {l.text}
              <span className="ml-2 text-xs opacity-70">{l.at}</span>
            </span>
          </li>
        ))}
      </ol>
      <p className="mt-2 text-xs">
        <span className="text-accent-ink">✦ Gemini</span> asks and writes ·{" "}
        <span className="text-verified">Exa</span> finds live pages ·{" "}
        <span className="text-ink">⚙ Rules</span> = plain code, no AI
      </p>
    </section>
  );
}
