"use client";

import { useState } from "react";
import { api, type Facts, type PlanResponse, type Question, type ReferralResponse } from "@/lib/api";
import { DeadlineCard, PlanBCard, QuestionChips, ReferralsCard, ThisWeekCard, TimelineCard } from "@/components/ui";

export default function Home() {
  const [text, setText] = useState("");
  const [facts, setFacts] = useState<Facts | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [refs, setRefs] = useState<ReferralResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [outOfScope, setOutOfScope] = useState<{ message: string; link: string } | null>(null);

  async function run<T>(fn: () => Promise<T>) {
    setLoading(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError("Something went wrong on our side. Your information is safe — please try again.");
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function buildPlan(f: Facts) {
    await run(async () => {
      const [p, r] = await Promise.all([api.plan(f), api.referrals(f)]);
      setPlan(p);
      setRefs(r);
    });
  }

  async function submit() {
    if (!text.trim()) return;
    setPlan(null);
    setRefs(null);
    setOutOfScope(null);
    const res = await run(() => api.intake(text));
    if (!res) return;
    if (res.out_of_scope || !res.facts) {
      setFacts(null);
      setQuestions([]);
      setOutOfScope({ message: res.message ?? "", link: res.link ?? "" });
      return;
    }
    setFacts(res.facts);
    setQuestions(res.missing_questions);
    if (res.missing_questions.length === 0) await buildPlan(res.facts);
  }

  async function answer(q: Question, value: string) {
    const next = { ...facts, [q.id]: value } as Facts;
    const remaining = questions.filter((x) => x.id !== q.id);
    setFacts(next);
    setQuestions(remaining);
    if (remaining.length === 0) await buildPlan(next);
  }

  const isMock = plan?.mock || refs?.mock;

  return (
    <main className="mx-auto max-w-2xl space-y-6 px-4 py-12">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold">What now?</h1>
        <p className="text-calm-700">
          Lost your job in Finland? Take a breath. Tell us in one sentence — we'll work out what matters this
          week.
        </p>
      </header>

      <div className="space-y-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), submit())}
          rows={3}
          placeholder="e.g. I was laid off yesterday as a software developer in Espoo, I'm on a work permit from India."
          className="w-full rounded-2xl border border-calm-100 bg-white p-4 text-base shadow-sm outline-none focus:ring-2 focus:ring-calm-500"
        />
        <button
          onClick={submit}
          disabled={loading || !text.trim()}
          className="rounded-full bg-calm-700 px-6 py-2.5 font-medium text-white disabled:opacity-40"
        >
          {loading ? "Thinking…" : "Show me what to do"}
        </button>
      </div>

      {error && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{error}</p>}

      {questions.length > 0 && (
        <section className="space-y-5 rounded-2xl bg-white p-6 shadow-sm ring-1 ring-calm-100">
          <p className="text-sm text-calm-500">
            {questions.length === 1 ? "One quick question" : `${questions.length} quick questions`} — just tap.
          </p>
          {questions.slice(0, 1).map((q) => (
            <QuestionChips key={q.id} q={q} onAnswer={(v) => answer(q, v)} />
          ))}
        </section>
      )}

      {plan && <DeadlineCard d={plan.deadline} />}
      {outOfScope && (
        <p className="rounded-xl bg-calm-50 p-4 text-sm text-calm-700">
          {outOfScope.message}{" "}
          {outOfScope.link && (
            <a className="underline" href={outOfScope.link} target="_blank" rel="noreferrer">
              Read more
            </a>
          )}
        </p>
      )}
      {plan && <ThisWeekCard actions={plan.this_week} />}
      {plan && plan.timeline.length > 0 && <TimelineCard weeks={plan.timeline} />}
      {plan && plan.plan_b.length > 0 && <PlanBCard options={plan.plan_b} />}
      {refs && <ReferralsCard r={refs} />}

      {plan && <p className="text-center text-xs text-calm-500">{plan.disclaimer}</p>}
      {isMock && (
        <p className="text-center text-xs text-calm-500">Demo mode: some results are sample data (no API keys set).</p>
      )}
    </main>
  );
}
