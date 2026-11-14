"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  chatStream, type ChatRequest, type Deadline, type Facts, type PlanResponse, type Question,
  type ReferralResponse, type StreamEvent,
} from "@/lib/api";
import type { Field } from "@/lib/facts";
import { toLogLine, type LogLine } from "@/lib/activity";
import { allLive, applyExaEvent, buildNodes, type NodeId, type Searching } from "@/lib/roadmap";
import { ActivityLog } from "@/components/ActivityLog";
import { Checklist } from "@/components/Checklist";
import { AskPanel, type AskEntry } from "@/components/AskPanel";
import { FlowProgress } from "@/components/FlowProgress";
import { HowWeKnow } from "@/components/HowWeKnow";
import { QuestionCard, Welcome } from "@/components/QuestionCard";
import { Legend, Roadmap, type AddedItem } from "@/components/Roadmap";
import { SituationStrip } from "@/components/SituationStrip";
import { Button, GentleWarning, cx } from "@/components/primitives";

type Tab = "roadmap" | "ask" | "how";

/** Everything about this person lives in this browser tab only (sessionStorage). No accounts. */
type Saved = {
  started: boolean;
  facts: Facts;
  question?: Question;
  built: boolean;
  tab: Tab;
  deadline?: Deadline;
  plan?: PlanResponse;
  referrals?: ReferralResponse;
  outOfScope?: { message: string; link?: string; links?: { title: string; url: string }[] };
  doneActions: Record<number, boolean>;
  doneNodes: Partial<Record<NodeId, boolean>>;
  drafts: Record<string, string>;
  asks: AskEntry[];
  added: Partial<Record<NodeId, AddedItem[]>>;
};

const KEY = "what-now-roadmap-v2";
const empty = (): Saved => ({
  started: false, facts: {}, built: false, tab: "roadmap", doneActions: {}, doneNodes: {}, drafts: {}, asks: [], added: {},
});

function load(): Saved {
  try {
    const raw = window.sessionStorage.getItem(KEY);
    return raw ? { ...empty(), ...JSON.parse(raw) } : empty();
  } catch {
    return empty();
  }
}

const TABS: { id: Tab; label: string }[] = [
  { id: "roadmap", label: "Roadmap" },
  { id: "ask", label: "Ask" },
  { id: "how", label: "How we know this" },
];

export default function StartPage() {
  const [s, setS] = useState<Saved>(empty);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [finding, setFinding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searching, setSearching] = useState<Searching>({});
  const [log, setLog] = useState<LogLine[]>([]);
  const [confirmClear, setConfirmClear] = useState(false);
  const [editing, setEditing] = useState<Field | null>(null);
  const [qVersion, setQVersion] = useState(0);
  const stripRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setS(load()); setLoaded(true); }, []);
  useEffect(() => {
    if (!loaded) return;
    try { window.sessionStorage.setItem(KEY, JSON.stringify(s)); } catch { /* storage blocked: still works */ }
  }, [s, loaded]);

  const update = (patch: Partial<Saved>) => setS((prev) => ({ ...prev, ...patch }));

  function onEvent(e: StreamEvent) {
    const line = toLogLine(e);
    if (line) setLog((cur) => [...cur, line].slice(-60));
    if (e.type === "progress" && e.stage !== "reading_situation") setFinding(true);
    if (e.type === "exa") setSearching((cur) => applyExaEvent(cur, e));
    if (e.type === "partial") update({ [e.key]: e.data } as Partial<Saved>);
  }

  async function send(req: Partial<ChatRequest>) {
    setBusy(true);
    setError(null);
    setSearching({});
    try {
      const res = await chatStream({ messages: [], facts: s.facts, step: "find_your_way_in", ...req }, onEvent);
      setQVersion((v) => v + 1);
      if (res.out_of_scope) {
        update({ facts: res.facts, outOfScope: { message: res.reply, link: res.link, links: res.links }, question: undefined });
      } else if (res.question) {
        update({ facts: res.facts, question: res.question, outOfScope: undefined });
      } else {
        update({
          facts: res.facts, question: undefined, outOfScope: undefined, built: true,
          deadline: res.deadline, plan: res.plan ?? s.plan, referrals: res.referrals ?? s.referrals,
        });
      }
    } catch {
      setError("Something went wrong on our side. Your answers are safe here. Please try again.");
    } finally {
      setBusy(false);
      setFinding(false);
      setSearching({});
    }
  }

  const nodes = useMemo(() => buildNodes({
    today: new Date(), ready: s.built || !!s.deadline, deadline: s.deadline, plan: s.plan, referrals: s.referrals,
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

  function pickExactDate() {
    setEditing("job_end_date");
    stripRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  if (!loaded) return null;

  if (!s.started)
    return (
      <main id="main" className="mx-auto max-w-7xl px-5 sm:px-8">
        <Welcome busy={busy} onSubmit={(text) => { update({ started: true }); send({ messages: [{ role: "user", text }] }); }} />
      </main>
    );

  const phase = s.built ? (s.tab === "ask" ? "ask" : "roadmap") : finding ? "finding" : "tell";
  const live = allLive(nodes);
  const anyLive = nodes.some((n) => n.live);

  return (
    <main id="main" className="mx-auto max-w-6xl space-y-8 px-5 pb-16 pt-8 sm:px-8 sm:pt-10">
      {/* Row 1: where you are */}
      <FlowProgress phase={phase} built={s.built} onGo={(p) => update({ tab: p })} />

      {/* Row 2: only the current step */}
      <div>
        {s.outOfScope ? (
          <section aria-labelledby="redirect-title" className="animate-fade-up mx-auto max-w-3xl space-y-5 rounded-3xl border border-rule bg-card p-6 sm:p-10">
            <h2 id="redirect-title" className="font-serif text-3xl font-semibold leading-snug">{s.outOfScope.message}</h2>
            <ul className="space-y-3">
              {(s.outOfScope.links?.length ? s.outOfScope.links : s.outOfScope.link ? [{ title: "InfoFinland", url: s.outOfScope.link }] : []).map((l) => (
                <li key={l.url}>
                  <a href={l.url} target="_blank" rel="noreferrer"
                    className="flex min-h-12 items-center justify-between gap-3 rounded-xl border border-rule bg-paper px-4 py-3 font-bold hover:border-ink">
                    {l.title}<span aria-hidden className="text-ink-soft">↗</span><span className="sr-only">(opens in a new tab)</span>
                  </a>
                </li>
              ))}
            </ul>
            <p className="text-ink-soft">Got something wrong? Tap a detail below to change it, or start over.</p>
          </section>
        ) : !s.built ? (
          finding ? (
            <section aria-labelledby="finding-title" className="animate-fade-up mx-auto max-w-3xl space-y-6 rounded-3xl border border-rule bg-card p-6 sm:p-10">
              <div>
                <h2 id="finding-title" className="font-serif text-3xl font-semibold sm:text-4xl">Finding the facts for you</h2>
                <p className="mt-2 text-lg text-ink-soft">Checking Migri&apos;s rules and searching official sites and the web, live. This takes a few seconds.</p>
              </div>
              <ActivityLog lines={log} busy={busy} last={3} />
            </section>
          ) : s.question ? (
            <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
              <div className="space-y-4">
                <QuestionCard key={`${s.question.id}-${qVersion}`} question={s.question} busy={busy}
                  onAnswer={(value) => send({ answers: { [s.question!.id]: value } as Partial<Facts> })}
                  onText={(text) => send({ messages: [{ role: "user", text }] })} />
                <ActivityLog lines={log} busy={busy} last={3} />
              </div>
              <Checklist facts={s.facts} />
            </div>
          ) : (
            <div className="mx-auto max-w-3xl space-y-4">
              <p className="font-serif text-2xl">Reading your situation…</p>
              <ActivityLog lines={log} busy={busy} last={3} />
            </div>
          )
        ) : (
          <div className="space-y-6">
            <div role="tablist" aria-label="Your roadmap" className="flex flex-wrap gap-2 border-b border-rule">
              {TABS.map((t) => (
                <button key={t.id} role="tab" id={`tab-${t.id}`} aria-selected={s.tab === t.id} aria-controls={`panel-${t.id}`}
                  onClick={() => update({ tab: t.id })}
                  className={cx("-mb-px min-h-12 rounded-t-xl border-b-2 px-4 font-bold",
                    s.tab === t.id ? "border-ink text-ink" : "border-transparent text-ink-soft hover:text-ink")}>
                  {t.label}
                </button>
              ))}
            </div>
            <div role="tabpanel" id={`panel-${s.tab}`} aria-labelledby={`tab-${s.tab}`}>
              {s.tab === "roadmap" && (
                <div className="space-y-6">
                  <div>
                    <h2 className="font-serif text-3xl font-semibold sm:text-4xl">Your roadmap</h2>
                    <p className="mt-2 text-lg text-ink-soft">
                      {busy ? "Updating with your change…"
                        : live ? "Everything here was found live today."
                        : anyLive ? "Most of this was found live today. Steps marked “saved guide” use our checked fallback."
                        : "Live data isn't available right now, so these steps use our checked saved guide."}
                    </p>
                  </div>
                  {busy && <ActivityLog lines={log} busy={busy} last={3} />}
                  <Roadmap
                    nodes={nodes}
                    data={s}
                    onToggleAction={(i) => update({ doneActions: { ...s.doneActions, [i]: !s.doneActions[i] } })}
                    onToggleNode={(id) => update({ doneNodes: { ...s.doneNodes, [id]: !s.doneNodes[id] } })}
                    onDraft={(url, text) => update({ drafts: { ...s.drafts, [url]: text } })}
                    onPickExactDate={pickExactDate}
                  />
                  <Legend />
                </div>
              )}
              {s.tab === "ask" && (
                <AskPanel facts={s.facts} entries={s.asks}
                  onEntry={(e) => update({ asks: [...s.asks, e] })}
                  onAdd={(i) => {
                    const e = s.asks[i];
                    const step = e.res.suggested_roadmap_step!;
                    update({
                      asks: s.asks.map((x, k) => (k === i ? { ...x, added: true } : x)),
                      added: { ...s.added, [step]: [...(s.added[step] ?? []), { question: e.question, answer: e.res.answer, sources: e.res.sources }] },
                    });
                  }} />
              )}
              {s.tab === "how" && <HowWeKnow embedded />}
            </div>
          </div>
        )}
      </div>

      {/* Row 3: your situation, one line, tap to edit */}
      <div ref={stripRef} className="space-y-3">
        <SituationStrip facts={s.facts} open={editing} onOpen={setEditing}
          onEdit={(field: Field, value) => send({ edited_facts: { [field]: value } as Partial<Facts> })} />
        {error && <GentleWarning>{error}</GentleWarning>}
        <div className="flex flex-wrap items-center gap-3">
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
    </main>
  );
}
