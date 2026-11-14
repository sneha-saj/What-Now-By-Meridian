/**
 * Saved roadmaps live in this browser only (localStorage). No accounts, nothing on a server.
 * Each entry is a snapshot of the /start session so it can be reopened later.
 */
export type SavedRoadmap<T> = { id: string; title: string; summary: string[]; savedAt: string; state: T };

const KEY = "what-now-saved-roadmaps";

export function listSaved<T>(): SavedRoadmap<T>[] {
  try {
    return JSON.parse(window.localStorage.getItem(KEY) ?? "[]");
  } catch {
    return [];
  }
}

function write<T>(items: SavedRoadmap<T>[]): boolean {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(items.slice(0, 10)));
    return true;
  } catch {
    return false; // storage full or blocked
  }
}

/** Save a roadmap with its own situation. Passing an existing id updates that entry instead of adding a copy. */
export function saveRoadmap<T>(title: string, summary: string[], state: T, id?: string): string | null {
  const entryId = id ?? String(Date.now());
  const entry = { id: entryId, title, summary, savedAt: new Date().toISOString(), state };
  return write([entry, ...listSaved<T>().filter((r) => r.id !== entryId)]) ? entryId : null;
}

export function deleteSaved(id: string) {
  write(listSaved().filter((r) => r.id !== id));
}
