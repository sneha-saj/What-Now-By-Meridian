"use client";

import { useId, useState } from "react";
import { getCode, loadHealth, setCode, useHealth } from "@/lib/access";
import { CheckIcon } from "./icons";
import { Button, cx } from "./primitives";

/** "Judge? Enter access code": only shown when the server uses access codes. With a valid code the app runs live
 *  (Exa, Gemini, Context.dev, ElevenLabs); without one it's the free demo. */
export function AccessCode({ className, initiallyOpen = false, onCancel }: {
  className?: string; initiallyOpen?: boolean; onCancel?: () => void;
}) {
  const health = useHealth();
  const inputId = useId();
  const [open, setOpen] = useState(initiallyOpen);
  const [text, setText] = useState("");
  const [state, setState] = useState<"idle" | "checking" | "wrong">("idle");
  if (!health?.access_codes) return null;

  if (health.live)
    return (
      <p className={cx("flex flex-wrap items-center gap-2 text-sm", className)}>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-verified-soft px-3 py-1 font-bold text-verified">
          <CheckIcon /> Live mode on
        </span>
        <span className="text-ink-soft">Access code accepted: searches and answers are live.</span>
        <button className="min-h-9 text-ink-soft underline" onClick={() => { setCode(""); loadHealth(true); }}>Remove code</button>
      </p>
    );

  async function check(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    const before = getCode();
    setCode(text);
    setState("checking");
    const h = await loadHealth(true);
    if (h.live) { setState("idle"); setOpen(false); return; }
    setCode(before);
    await loadHealth(true);
    setState("wrong");
  }

  return (
    <div className={cx("text-sm", className)}>
      {!open ? (
        <p className="text-ink-soft">
          Demo mode: live search and voice are off.{" "}
          <button className="min-h-9 font-bold text-ink underline" onClick={() => setOpen(true)}>Judge? Enter access code</button>
        </p>
      ) : (
        <form onSubmit={check} className="flex flex-wrap items-center gap-2">
          <label htmlFor={inputId} className="font-bold">Access code</label>
          <input id={inputId} value={text} autoFocus autoComplete="off" onChange={(e) => { setText(e.target.value); setState("idle"); }}
            className="min-h-11 w-48 rounded-xl border border-ink/25 bg-card px-3" />
          <Button type="submit" variant="chip" disabled={!text.trim() || state === "checking"}>{state === "checking" ? "Checking…" : "Use code"}</Button>
          <Button type="button" variant="quiet" onClick={() => { setOpen(false); onCancel?.(); }}>Cancel</Button>
          {state === "wrong" && <span role="alert" className="basis-full text-warn">That code didn&apos;t work. Check it and try again.</span>}
        </form>
      )}
    </div>
  );
}

/** Shown above the steps in demo mode, so nobody mistakes the saved guide for a live search. */
export function DemoModeNote() {
  const health = useHealth();
  if (!health?.access_codes || health.live) return null;
  return (
    <div role="note" className="space-y-1 rounded-2xl border border-rule bg-paper-deep/60 px-5 py-4">
      <p className="font-bold">Demo mode: no live search</p>
      <p className="text-ink-soft">
        How long you can stay is still worked out from the official rules. The steps come from our checked saved guide, and
        perks, Ask and voice need live mode.
      </p>
      <AccessCode />
    </div>
  );
}
