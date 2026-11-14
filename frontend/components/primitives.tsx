import type { Source } from "@/lib/api";

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

export function formatDate(iso: string) {
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
}

export function hostOf(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function Card({
  title,
  children,
  className,
  as: Tag = "section",
}: {
  title?: string;
  children: React.ReactNode;
  className?: string;
  as?: "section" | "article" | "div";
}) {
  return (
    <Tag className={cx("rounded-2xl border border-rule bg-card p-5 shadow-[0_1px_0_rgba(28,42,69,0.04)] sm:p-7", className)}>
      {title && <h2 className="mb-4 font-serif text-2xl font-semibold">{title}</h2>}
      {children}
    </Tag>
  );
}

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "quiet" | "chip" };

export function Button({ variant = "primary", className, ...props }: ButtonProps) {
  return (
    <button
      {...props}
      className={cx(
        "inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-5 py-2.5 font-bold transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" && "bg-ink text-paper hover:bg-ink/90",
        variant === "quiet" && "text-ink-soft underline decoration-rule underline-offset-4 hover:text-ink hover:decoration-ink",
        variant === "chip" && "border border-ink/25 bg-card px-4 font-normal text-ink hover:border-ink hover:bg-paper-deep",
        className,
      )}
    />
  );
}

/** Title + domain; opens the official page in a new tab. */
export function SourceChip({ source }: { source: Source }) {
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noreferrer"
      title={source.highlight ?? source.title}
      className="inline-flex min-h-9 max-w-full items-center gap-1.5 rounded-lg border border-rule bg-paper px-2.5 py-1 text-sm hover:border-ink-soft"
    >
      <span className="truncate">{source.title}</span>
      <span className="shrink-0 text-ink-soft">· {hostOf(source.url)}</span>
      <span aria-hidden className="shrink-0 text-ink-soft">↗</span>
      <span className="sr-only">(opens in a new tab)</span>
    </a>
  );
}

export function Sources({ sources, label = "Source" }: { sources: Source[]; label?: string }) {
  if (!sources.length) return null;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <span className="text-sm text-ink-soft">{sources.length > 1 ? `${label}s` : label}:</span>
      {sources.map((s) => (
        <SourceChip key={s.url} source={s} />
      ))}
    </div>
  );
}

export function VerifiedBadge() {
  return (
    <a
      href="/how-we-know"
      className="inline-flex min-h-9 items-center gap-1.5 rounded-full bg-verified-soft px-3 py-1 text-sm font-bold text-verified hover:underline"
    >
      <span aria-hidden>✓</span> Checked against Migri today
    </a>
  );
}

export function GentleWarning({ children }: { children: React.ReactNode }) {
  return (
    <div role="status" className="rounded-xl bg-warn-soft px-4 py-3 text-warn">
      {children}
    </div>
  );
}
