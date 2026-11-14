import type { ChatMessage, ChatResponse, Facts, Step } from "./api";

/** Everything about this person lives here, in this browser tab only. No accounts, no server storage. */
export type Session = {
  messages: ChatMessage[];
  facts: Facts;
  confirmed: (keyof Facts)[];
  step: Step | null;
  last: ChatResponse | null;
  done: Record<number, boolean>;
  drafts: Record<string, string>;
};

const KEY = "what-now-session";

export const emptySession = (): Session => ({
  messages: [], facts: {}, confirmed: [], step: null, last: null, done: {}, drafts: {},
});

export function loadSession(): Session {
  try {
    const raw = window.sessionStorage.getItem(KEY);
    return raw ? { ...emptySession(), ...JSON.parse(raw) } : emptySession();
  } catch {
    return emptySession();
  }
}

export function saveSession(s: Session) {
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    // Private mode or storage blocked: the app still works, it just won't survive a reload.
  }
}

export function clearSession() {
  try {
    window.sessionStorage.removeItem(KEY);
  } catch {}
}
