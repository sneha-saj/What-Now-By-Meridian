"use client";

import { useEffect, useRef, useState } from "react";
import { cx } from "./primitives";

/** "Open all / Close all" for the foldable sections (<details>) inside `target`. The label follows the sections,
 *  also when they're opened or closed one by one. */
export function ExpandAll({ target, className }: { target: React.RefObject<HTMLElement | null>; className?: string }) {
  const [allOpen, setAllOpen] = useState(false);
  const wantOpen = useRef(false); // after "Open all", sections that load later (e.g. source groups) open too
  useEffect(() => {
    const el = target.current;
    if (!el) return;
    const obs = new MutationObserver(() => {
      if (wantOpen.current) el.querySelectorAll("details:not([open])").forEach((d) => { (d as HTMLDetailsElement).open = true; });
    });
    obs.observe(el, { childList: true, subtree: true });
    return () => obs.disconnect();
  }, [target]);
  useEffect(() => {
    const el = target.current;
    if (!el) return;
    const update = (e?: Event) => {
      if (e && !(e.target as HTMLDetailsElement).open) wantOpen.current = false; // closed by hand: stop auto-opening
      const sections = Array.from(el.querySelectorAll("details"));
      setAllOpen(sections.length > 0 && sections.every((d) => d.open));
    };
    update();
    el.addEventListener("toggle", update, true); // "toggle" doesn't bubble, so listen while it travels down
    return () => el.removeEventListener("toggle", update, true);
  }, [target]);

  return (
    <button type="button"
      onClick={() => {
        wantOpen.current = !allOpen;
        target.current?.querySelectorAll("details").forEach((d) => { d.open = !allOpen; });
      }}
      className={cx("inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-full border border-ink/20 bg-card px-3 py-1 text-sm font-bold text-ink hover:border-ink", className)}>
      <svg aria-hidden viewBox="0 0 20 20" className={cx("h-4 w-4 transition-transform", allOpen && "rotate-180")}>
        <path d="M5 7.5l5 5 5-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {allOpen ? "Close all" : "Open all"}
    </button>
  );
}
