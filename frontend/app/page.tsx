import { CheckIcon, GlobeIcon, PersonIcon } from "@/components/icons";

const STEPS = [
  {
    title: "Your deadline",
    text: "How long you can stay to find a new job: 3 or 6 months, worked out from your permit and checked against Migri's page the same day.",
  },
  {
    title: "This week",
    text: "The three most useful things to do now, like registering as a jobseeker and checking Kela support, each with its official source.",
  },
  {
    title: "Week by week, and a Plan B",
    text: "A roadmap from today to your deadline, plus other permits that could fit you and the latest date to start them.",
  },
  {
    title: "Find your way in",
    text: "Companies hiring now, people who could refer you, and communities and events. With a short draft message you send yourself.",
  },
];

export default function Home() {
  return (
    <main id="main" className="mx-auto max-w-7xl px-5 pb-20 sm:px-8">
      <section className="grid gap-10 py-12 sm:py-20 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:items-end">
        <div className="space-y-6">
          <h1 className="animate-fade-up font-serif text-5xl font-semibold leading-[1.05] sm:text-7xl">
            Laid off? Let&apos;s figure out what&apos;s next.
          </h1>
          <p className="max-w-2xl text-xl sm:text-2xl">
            Find out how long you can stay, what to do this week, and who can refer you to a new job.
          </p>
          <div className="flex flex-wrap items-center gap-4 pt-2">
            <a href="/start" className="inline-flex min-h-12 items-center rounded-xl bg-ink px-6 py-3 text-lg font-bold text-paper hover:bg-ink/90">
              Let&apos;s start
            </a>
            <span className="text-ink-soft">Takes about 2 minutes. No account.</span>
          </div>
          <p className="text-sm text-ink-soft">Currently for people in Finland. More countries coming.</p>
        </div>

        <aside aria-label="How it works" className="rounded-3xl border border-rule bg-card p-6 shadow-[0_6px_24px_rgba(28,42,69,0.06)] sm:p-8">
          <p className="font-serif text-2xl font-semibold">How it works</p>
          <ol className="mt-4 space-y-4">
            <li className="flex gap-3"><PersonIcon className="mt-1 h-5 w-5 text-accent-ink" /><span><strong>You tell us</strong> what happened in a sentence. We ask only what&apos;s missing.</span></li>
            <li className="flex gap-3"><GlobeIcon className="mt-1 h-5 w-5 text-verified" /><span><strong>Exa searches live</strong> on Migri, Kela, InfoFinland and Työmarkkinatori, and the web for jobs and people.</span></li>
            <li className="flex gap-3"><CheckIcon className="mt-1 h-5 w-5 text-verified" /><span><strong>Your roadmap builds itself</strong>, step by step, every fact with its source.</span></li>
          </ol>
        </aside>
      </section>

      <section aria-labelledby="what-title" className="border-t border-rule py-12">
        <h2 id="what-title" className="font-serif text-3xl font-semibold sm:text-4xl">What you get</h2>
        <ul className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <li key={s.title} className="rounded-2xl border border-rule bg-card p-6">
              <span className="font-serif text-lg text-accent-ink">{i + 1}</span>
              <p className="mt-1 font-serif text-xl font-semibold">{s.title}</p>
              <p className="mt-2 text-ink-soft">{s.text}</p>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="trust-title" className="grid gap-8 border-t border-rule py-12 lg:grid-cols-3">
        <h2 id="trust-title" className="font-serif text-3xl font-semibold">Why you can trust it</h2>
        <ul className="space-y-3 text-lg lg:col-span-2">
          <li>Sourced from Migri, Kela, InfoFinland and Työmarkkinatori. Every step links to the page it came from.</li>
          <li>The deadline is worked out by plain code from Migri&apos;s rules, not guessed by AI. <a href="/how-we-know" className="underline">How we know this</a>.</li>
          <li>Nothing is stored on a server and nothing is sent for you. Draft messages are yours to edit and send.</li>
          <li className="text-ink-soft">Guidance, not legal advice. For permit decisions, contact Migri or your union.</li>
        </ul>
      </section>
    </main>
  );
}
