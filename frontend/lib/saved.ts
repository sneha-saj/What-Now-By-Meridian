/**
 * Saved roadmaps live in this browser only (localStorage). No accounts, nothing on a server.
 * Each entry is a snapshot of the /start session so it can be reopened later.
 */
export type SavedRoadmap<T> = { id: string; title: string; savedAt: string; state: T };

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

export function saveRoadmap<T>(title: string, state: T): boolean {
  const entry = { id: String(Date.now()), title, savedAt: new Date().toISOString(), state };
  return write([entry, ...listSaved<T>()]);
}

export function deleteSaved(id: string) {
  write(listSaved().filter((r) => r.id !== id));
}
