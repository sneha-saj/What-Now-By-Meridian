import { CheckIcon, GlobeIcon, PersonIcon } from "@/components/icons";

const SOURCES = ["migri.fi", "kela.fi", "infofinland.fi", "tyomarkkinatori.fi"];

const GET = [
  { n: "1", title: "How long you can stay", text: "3 or 6 months, checked against Migri today." },
  { n: "2", title: "Your next steps, in order", text: "Each one linked to its official source." },
  { n: "3", title: "Perks and support", text: "Job search certificate, city discounts and hiring incentives." },
];

/** A small, labelled example of the first steps, joined by the signature amber "meridian" line. */
function StepsPreview() {
  return (
    <figure aria-label="Example steps" className="relative rounded-[2rem] border border-rule bg-card p-6 shadow-[0_24px_60px_-24px_rgba(28,42,69,0.25)] sm:p-8">
      <figcaption className="absolute -top-3 left-6 rounded-full bg-ink px-3 py-1 text-xs font-bold text-paper">Example steps</figcaption>
      <p className="font-serif text-3xl font-semibold leading-tight sm:text-4xl">Your first steps</p>

      <ol className="relative mt-6 space-y-5">
        <span aria-hidden className="animate-draw-down absolute bottom-2 left-[9px] top-2 w-[2px] rounded bg-accent" />
        {[
          { t: "Register as a jobseeker", s: "tyomarkkinatori.fi" },
          { t: "Check Kela support", s: "kela.fi" },
          { t: "Get your job search certificate", s: "tyomarkkinatori.fi" },
        ].map((x, i) => (
          <li key={x.t} className="animate-fade-up relative flex items-start gap-4" style={{ animationDelay: `${200 + i * 120}ms` }}>
            <span aria-hidden className="relative z-10 mt-1 h-5 w-5 shrink-0 rounded-full border-2 border-accent bg-accent" />
            <span>
              <span className="block font-bold">{x.t}</span>
              <span className="mt-0.5 inline-flex items-center gap-1 text-sm text-ink-soft">
                <GlobeIcon className="h-3.5 w-3.5 text-verified" /> Found live · {x.s}
              </span>
            </span>
          </li>
        ))}
      </ol>
    </figure>
  );
}

export default function Home() {
  return (
    <main id="main" className="overflow-hidden">
      {/* Hero */}
      <section className="mx-auto grid max-w-6xl items-center gap-12 px-5 pb-16 pt-12 sm:px-8 sm:pt-20 lg:grid-cols-[1.1fr_0.9fr] lg:gap-16 lg:pb-24">
        <div>
          <h1 aria-label="Lost your job? Let's figure out what's next." className="animate-fade-up font-serif text-5xl font-semibold leading-[1.02] tracking-tight sm:text-7xl">
            <span aria-hidden="true" className="hero-rotating text-4xl sm:text-7xl">
              <span>Laid off?</span><span>Lost your job?</span><span>Contract ended?</span>
            </span><br />
            <span className="text-accent-ink">Let&apos;s figure out</span> what&apos;s next.
          </h1>
          <p className="mt-6 max-w-md text-xl text-ink-soft">
            How long you can stay, your next steps in order, and the perks and support you can get.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-x-5 gap-y-3">
            <a href="/start" className="inline-flex min-h-14 items-center gap-2 rounded-2xl bg-ink px-7 text-lg font-bold text-paper shadow-sm hover:bg-ink/90">
              Let&apos;s start <span aria-hidden>→</span>
            </a>
            <span className="text-ink-soft">2 minutes · no account</span>
          </div>
          <p className="mt-6 inline-flex items-center gap-2 rounded-full border border-rule px-3 py-1 text-sm text-ink-soft">
            <span aria-hidden>🇫🇮</span> For people in Finland. More countries coming.
          </p>
        </div>
        <StepsPreview />
      </section>

      {/* What you get: three short tiles */}
      <section aria-label="What you get" className="border-y border-rule bg-paper-deep/60">
        <ul className="mx-auto grid max-w-6xl gap-px px-5 sm:grid-cols-3 sm:px-8">
          {GET.map((g) => (
            <li key={g.n} className="py-8 sm:px-6 sm:first:pl-0">
              <span className="font-serif text-3xl text-accent-ink">{g.n}</span>
              <p className="mt-1 font-serif text-2xl font-semibold">{g.title}</p>
              <p className="mt-1 text-ink-soft">{g.text}</p>
            </li>
          ))}
        </ul>
      </section>

      {/* How it works: one line */}
      <section aria-label="How it works" className="mx-auto max-w-6xl px-5 py-14 sm:px-8">
        <ol className="flex flex-col gap-4 text-lg sm:flex-row sm:items-center sm:gap-3">
          <li className="flex items-center gap-2"><PersonIcon className="h-5 w-5 text-accent-ink" /> You tell us what happened</li>
          <li aria-hidden className="hidden h-px flex-1 bg-accent sm:block" />
          <li className="flex items-center gap-2"><GlobeIcon className="h-5 w-5 text-verified" /> Exa searches official sites live</li>
          <li aria-hidden className="hidden h-px flex-1 bg-accent sm:block" />
          <li className="flex items-center gap-2"><CheckIcon className="h-5 w-5 text-verified" /> Your next steps, every fact sourced</li>
        </ol>

        <div className="mt-12 flex flex-col gap-3 border-t border-rule pt-6 text-sm text-ink-soft sm:flex-row sm:items-center sm:justify-between">
          <p>
            Sourced from{" "}
            {SOURCES.map((s, i) => (
              <span key={s}><span className="font-bold text-ink">{s}</span>{i < SOURCES.length - 1 ? " · " : ""}</span>
            ))}
          </p>
          <p>
            Guidance, not legal advice · <a href="/how-we-know" className="underline">How we know this</a>
          </p>
        </div>
      </section>
    </main>
  );
}
