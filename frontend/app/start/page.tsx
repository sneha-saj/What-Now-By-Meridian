"use client";

import { useEffect, useMemo, useState } from "react";
import {
  chatStream, type ChatRequest, type Deadline, type Facts, type PlanResponse, type Question,
  type ReferralResponse, type StreamEvent,
} from "@/lib/api";
import type { Field } from "@/lib/facts";
import { applyExaEvent, buildNodes, type NodeId, type Searching } from "@/lib/roadmap";
import { toLogLine, type LogLine } from "@/lib/activity";
import { ActivityLog } from "@/components/ActivityLog";
import { Legend, Roadmap } from "@/components/Roadmap";
import { QuestionCard, Welcome } from "@/components/QuestionCard";
import { SituationStrip } from "@/components/SituationStrip";
import { Button, GentleWarning } from "@/components/primitives";

/** Everything about this person lives in this browser tab only (sessionStorage). No accounts. */
type Saved = {
  started: boolean;
  facts: Facts;
  question?: Question;
  ready: boolean;
  deadline?: Deadline;
  plan?: PlanResponse;
  referrals?: ReferralResponse;
  outOfScope?: { message: string; link?: string };
  doneActions: Record<number, boolean>;
  doneNodes: Partial<Record<NodeId, boolean>>;
  drafts: Record<string, string>;
};

const KEY = "what-now-roadmap";
const empty = (): Saved => ({ started: false, facts: {}, ready: false, doneActions: {}, doneNodes: {}, drafts: {} });

function load(): Saved {
  try {
    const raw = window.sessionStorage.getItem(KEY);
    return raw ? { ...empty(), ...JSON.parse(raw) } : empty();
  } catch {
    return empty();
  }
}

export default function StartPage() {
  const [s, setS] = useState<Saved>(empty);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searching, setSearching] = useState<Searching>({});
  const [confirmClear, setConfirmClear] = useState(false);
  const [log, setLog] = useState<LogLine[]>([]);

  useEffect(() => { setS(load()); setLoaded(true); }, []);
  useEffect(() => {
    if (!loaded) return;
    try { window.sessionStorage.setItem(KEY, JSON.stringify(s)); } catch { /* storage blocked: still works */ }
  }, [s, loaded]);

  const update = (patch: Partial<Saved>) => setS((prev) => ({ ...prev, ...patch }));

  function onEvent(e: StreamEvent) {
    const line = toLogLine(e);
    if (line) setLog((cur) => [...cur, line].slice(-60));
    if (e.type === "exa") setSearching((cur) => applyExaEvent(cur, e));
    else if (e.type === "partial") update({ [e.key]: e.data, ready: true, question: undefined } as Partial<Saved>);
  }

  async function send(req: Partial<ChatRequest>) {
    setBusy(true);
    setError(null);
    setSearching({});
    try {
      const res = await chatStream({ messages: [], facts: s.facts, step: "find_your_way_in", ...req }, onEvent);
      if (res.out_of_scope) {
        update({ outOfScope: { message: res.reply, link: res.link }, question: undefined });
        return;
      }
      if (res.question) {
        update({ facts: res.facts, question: res.question, ready: false, outOfScope: undefined });
        return;
      }
      update({
        facts: res.facts, question: undefined, ready: true, outOfScope: undefined,
        deadline: res.deadline, plan: res.plan ?? s.plan, referrals: res.referrals ?? s.referrals,
      });
    } catch {
      setError("Something went wrong on our side. Your answers are safe here. Please try again.");
    } finally {
      setBusy(false);
      setSearching({});
    }
  }

  const nodes = useMemo(() => buildNodes({
    today: new Date(), ready: s.ready, deadline: s.deadline, plan: s.plan, referrals: s.referrals,
    searching, doneActions: s.doneActions, doneNodes: s.doneNodes,
  }), [s, searching]);

  function clearAll() {
    try { window.sessionStorage.removeItem(KEY); } catch {}
    setS(empty());
    setSearching({});
    setLog([]);
    setConfirmClear(false);
    setError(null);
  }

  if (!loaded) return null;

  if (!s.started)
    return (
      <main id="main" className="mx-auto max-w-7xl px-5 sm:px-8">
        <Welcome busy={busy} onSubmit={(text) => { update({ started: true }); send({ messages: [{ role: "user", text }] }); }} />
      </main>
    );

  const someSample = (s.plan?.mock || s.referrals?.mock) && s.ready;

  return (
    <main id="main" className="mx-auto max-w-7xl px-5 pb-16 pt-8 sm:px-8 sm:pt-12">
      <div className="grid gap-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-14">
        {/* Left: the one question, then what we know about you */}
        <div className="space-y-8 lg:sticky lg:top-8 lg:self-start">
          {s.outOfScope ? (
            <GentleWarning>
              <p>{s.outOfScope.message}</p>
              {s.outOfScope.link && <a href={s.outOfScope.link} target="_blank" rel="noreferrer" className="font-bold underline">Read more on InfoFinland</a>}
            </GentleWarning>
          ) : s.question ? (
            <QuestionCard question={s.question} busy={busy}
              onAnswer={(value) => send({ answers: { [s.question!.id]: value } as Partial<Facts> })}
              onText={(text) => send({ messages: [{ role: "user", text }] })} />
          ) : s.ready ? (
            <section className="animate-fade-up rounded-3xl border border-rule bg-card p-6 sm:p-8">
              <p className="font-serif text-2xl font-semibold sm:text-3xl">{busy ? "Building your roadmap…" : "Your roadmap is ready."}</p>
              <p className="mt-2 text-ink-soft">
                {busy ? "Exa is reading official pages and searching for people who can help, right now."
                  : "Everything on it was found live today. Open a step to see what to do and where it comes from."}
              </p>
            </section>
          ) : (
            <p className="text-ink-soft">Reading your situation…</p>
          )}

          <SituationStrip facts={s.facts} onEdit={(field: Field, value) => send({ edited_facts: { [field]: value } as Partial<Facts> })} />

          <ActivityLog lines={log} busy={busy} />

          {error && <GentleWarning>{error}</GentleWarning>}

          <div className="flex flex-wrap items-center gap-3 border-t border-rule pt-5">
            {confirmClear ? (
              <>
                <span>Clear everything you entered?</span>
                <Button variant="chip" onClick={clearAll}>Yes, clear my data</Button>
                <Button variant="quiet" onClick={() => setConfirmClear(false)}>Keep it</Button>
              </>
            ) : (
              <Button variant="quiet" onClick={() => setConfirmClear(true)}>Start over / clear my data</Button>
            )}
          </div>
        </div>

        {/* Right: the live roadmap */}
        <div className="space-y-8">
          {nodes.length > 0 ? (
            <Roadmap
              nodes={nodes}
              data={{ ...s }}
              onToggleAction={(i) => update({ doneActions: { ...s.doneActions, [i]: !s.doneActions[i] } })}
              onToggleNode={(id) => update({ doneNodes: { ...s.doneNodes, [id]: !s.doneNodes[id] } })}
              onDraft={(url, text) => update({ drafts: { ...s.drafts, [url]: text } })}
            />
          ) : (
            <section aria-label="Your roadmap" className="rounded-3xl border-2 border-dashed border-rule p-6 sm:p-8">
              <p className="font-serif text-2xl font-semibold">Your roadmap will appear here</p>
              <p className="mt-2 text-ink-soft">
                Once I know a few things about you, I&apos;ll check Migri&apos;s rules and search official Finnish sites
                and the web live, step by step: from today to your deadline.
              </p>
            </section>
          )}
          {someSample && (
            <p className="text-sm text-ink-soft">Some steps use our saved guide because live data isn&apos;t available right now. They&apos;re marked &quot;saved guide&quot;.</p>
          )}
          <Legend />
        </div>
      </div>
    </main>
  );
}
