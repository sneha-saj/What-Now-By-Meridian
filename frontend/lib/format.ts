/** "today", "yesterday", "3 days ago", "2 weeks ago", "4 months ago", or a date for older pages. */
export function ago(iso?: string | null, now = new Date()): string | null {
  if (!iso) return null;
  const d = new Date(iso.length === 10 ? iso + "T00:00:00" : iso);
  if (Number.isNaN(d.getTime())) return null;
  const days = Math.floor((now.getTime() - d.getTime()) / 86_400_000);
  if (days < 0) return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 14) return `${days} days ago`;
  if (days < 60) return `${Math.round(days / 7)} weeks ago`;
  if (days < 365) return `${Math.round(days / 30)} months ago`;
  return d.toLocaleDateString("en-GB", { month: "short", year: "numeric" });
}

/** Sample data in the saved example uses example.com; never mark it as found live. */
export const isSample = (url?: string | null) => !!url && /(^|\.|\/\/)example\.com/.test(url);
