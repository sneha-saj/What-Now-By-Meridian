"use client";

import { useEffect, useState } from "react";
import { cx } from "@/components/primitives";

/**
 * Cycles through short phrases with a gentle fade/slide-up. Purely visual: it is aria-hidden, so the
 * surrounding heading must carry the readable sentence (e.g. in an sr-only span).
 *
 * All phrases sit in the same grid cell, so the box is always as wide and tall as the longest one and
 * nothing around it moves. Rotation stops while `paused`, while the tab is hidden, and entirely under
 * prefers-reduced-motion (then `staticPhrase` is shown).
 */
export function RotatingPhrase({ phrases, interval = 2500, paused = false, staticPhrase, className }: {
  phrases: string[];
  interval?: number;
  paused?: boolean;
  staticPhrase?: string;
  className?: string;
}) {
  const [index, setIndex] = useState(0);
  const [hidden, setHidden] = useState(false);
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onMotion = () => setReduced(mq.matches);
    const onVisibility = () => setHidden(document.visibilityState === "hidden");
    onMotion();
    onVisibility();
    mq.addEventListener("change", onMotion);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      mq.removeEventListener("change", onMotion);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  const running = !paused && !hidden && !reduced && phrases.length > 1;
  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => setIndex((i) => (i + 1) % phrases.length), interval);
    return () => window.clearInterval(id);
  }, [running, interval, phrases.length]);

  if (reduced) {
    return <span aria-hidden="true" className={className}>{staticPhrase ?? phrases[0]}</span>;
  }

  const prev = (index - 1 + phrases.length) % phrases.length;
  return (
    <span aria-hidden="true" className={cx("inline-grid", className)}>
      {phrases.map((p, i) => (
        <span key={p}
          className={cx(
            "col-start-1 row-start-1 transition-[opacity,transform] duration-[350ms] ease-out",
            i === index ? "translate-y-0 opacity-100"
              : i === prev ? "-translate-y-3 opacity-0"
              : "translate-y-3 opacity-0",
          )}>
          {p}
        </span>
      ))}
    </span>
  );
}
