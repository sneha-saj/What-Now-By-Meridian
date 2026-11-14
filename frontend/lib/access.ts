"use client";

import { useEffect, useState } from "react";

/** Access code for judges: kept in this browser only, sent with every API request as X-Access-Code.
 *  Without a valid code (when the server requires one) the app runs in free demo mode. */
const KEY = "what-now-access-code";

export function getCode(): string {
  try {
    return window.localStorage.getItem(KEY) ?? "";
  } catch {
    return "";
  }
}

export function setCode(code: string) {
  try {
    if (code.trim()) window.localStorage.setItem(KEY, code.trim());
    else window.localStorage.removeItem(KEY);
  } catch { /* storage blocked: the code just won't be remembered */ }
}

/** Headers for an API request, with the access code if there is one. */
export function accessHeaders(headers: Record<string, string> = {}): Record<string, string> {
  const code = typeof window === "undefined" ? "" : getCode();
  return code ? { ...headers, "X-Access-Code": code } : headers;
}

/** A link like /start?code=… saves the code and removes it from the address bar. */
function captureCodeFromUrl() {
  try {
    const url = new URL(window.location.href);
    const code = url.searchParams.get("code");
    if (code) {
      setCode(code);
      url.searchParams.delete("code");
      window.history.replaceState(null, "", url.pathname + url.search + url.hash);
    }
  } catch { /* ignore */ }
}

export type Health = { live?: boolean; access_codes?: boolean; voice?: boolean };

let healthPromise: Promise<Health> | null = null;
const listeners = new Set<(h: Health) => void>();

/** What the server allows for this browser (live or demo, voice). `force` re-asks, e.g. after entering a code. */
export function loadHealth(force = false): Promise<Health> {
  if (force || !healthPromise) {
    captureCodeFromUrl();
    healthPromise = fetch("/api/health", { headers: accessHeaders() }).then((r) => r.json()).catch(() => ({}));
    healthPromise.then((h) => listeners.forEach((l) => l(h)));
  }
  return healthPromise;
}

export function useHealth(): Health | null {
  const [health, setHealth] = useState<Health | null>(null);
  useEffect(() => {
    listeners.add(setHealth);
    loadHealth().then(setHealth);
    return () => { listeners.delete(setHealth); };
  }, []);
  return health;
}
