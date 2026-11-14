"use client";

import { useId, useState } from "react";
import { getCode, loadHealth, setCode, useHealth } from "@/lib/access";
import { CheckIcon } from "./icons";
import { Button, cx } from "./primitives";

// Public by design. The hosted ACCESS_CODES allowlist must include this code too.
export const PUBLIC_TRIAL_CODE = "meridian-live-trial-r8n4";

/** Demo is the default. Visitors can enter a private code or deliberately reveal the public trial code. */
export function AccessCode({ className, initiallyOpen = false, onCancel }: {
  className?: string; initiallyOpen?: boolean; onCancel?: () => void;
}) {
  const health = useHealth();
  const inputId = useId();
  const [open, setOpen] = useState(initiallyOpen);
  const [text, setText] = useState("");
  const [state, setState] = useState<"idle" | "checking" | "wrong">("idle");
  const [revealTrial, setRevealTrial] = useState(false);
  const [copied, setCopied] = useState(false);
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
        <div className="space-y-2">
          <p className="text-ink-soft">You&apos;re in demo mode. Live search and voice are off.</p>
          <button type="button" className="min-h-9 font-bold text-ink underline" onClick={() => setOpen(true)}>Try the live version</button>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-ink-soft">Live search and voice use limited API credits. Please keep your test brief so others can try it too.</p>
          <form onSubmit={check} className="flex flex-wrap items-center gap-2">
            <label htmlFor={inputId} className="font-bold">Access code</label>
            <input id={inputId} value={text} autoFocus autoComplete="off" onChange={(e) => { setText(e.target.value); setState("idle"); }}
              className="min-h-11 w-48 rounded-xl border border-ink/25 bg-card px-3" />
            <Button type="submit" variant="chip" disabled={!text.trim() || state === "checking"}>{state === "checking" ? "Checking…" : "Use code"}</Button>
            <Button type="button" variant="quiet" onClick={() => { setOpen(false); onCancel?.(); }}>Stay in demo</Button>
            {state === "wrong" && <span role="alert" className="basis-full text-warn">That code didn&apos;t work. Check it and try again.</span>}
          </form>
          {!revealTrial ? (
            <button type="button" className="min-h-9 font-bold text-ink underline" onClick={() => setRevealTrial(true)}>No code? Reveal a trial code</button>
          ) : (
            <div className="flex flex-wrap items-center gap-2 rounded-xl border border-rule bg-paper p-3">
              <span className="text-ink-soft">Trial code:</span>
              <code className="select-all font-bold">{PUBLIC_TRIAL_CODE}</code>
              <Button type="button" variant="chip" onClick={async () => {
                try { await navigator.clipboard.writeText(PUBLIC_TRIAL_CODE); setCopied(true); }
                catch { setCopied(false); }
              }}>{copied ? "Copied" : "Copy code"}</Button>
            </div>
          )}
        </div>
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
