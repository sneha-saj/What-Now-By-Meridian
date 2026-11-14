"use client";

import { useEffect, useRef, useState } from "react";
import {
  chatStream, opportunitiesStream, stepsUpdateStream, type ChatRequest, type OpportunitiesResponse, type Deadline, type Facts, type PlanResponse, type Question,
  type StreamEvent,
} from "@/lib/api";
import type { Field } from "@/lib/facts";
import { toLogLine, type LogLine } from "@/lib/activity";
import { applyExaEvent, type Searching } from "@/lib/roadmap";
import { flattenSteps } from "@/lib/steps";
import { ActivityLog } from "@/components/ActivityLog";
import { Checklist } from "@/components/Checklist";
import { AskPanel, type AskEntry } from "@/components/AskPanel";
import { FlowProgress } from "@/components/FlowProgress";
import { HowWeKnow } from "@/components/HowWeKnow";
import { Opportunities } from "@/components/Opportunities";
import { QuestionCard, Welcome } from "@/components/QuestionCard";
import { Legend, Steps, type AddedItem, type Proposal } from "@/components/Steps";
import { deleteSaved, listSaved, saveRoadmap, type SavedRoadmap } from "@/lib/saved";
import { FIELDS, display } from "@/lib/facts";
import { Button, GentleWarning, cx } from "@/components/primitives";

/** Rotating first half of the landing headline ("… Let's figure out what's next."), shown in this order. */
const HEADLINE_PHRASES = [
  "Laid off?",
  "Contract ended?",
  "Lost your job?",
  "Fixed-term contract over?",
  "Probation ended?",
  "Made redundant?",
];

type StepAnchor = "week1" | "deadline";
type Tab = "roadmap" | "opportunities" | "how";

/** Everything about this person lives in this browser tab only (sessionStorage). No accounts. */
type Saved = {
  started: boolean;
  facts: Facts;
  question?: Question;
  built: boolean;
  tab: Tab;
  deadline?: Deadline;
  plan?: PlanResponse;
  outOfScope?: { message: string; link?: string; links?: { title: string; url: string }[] };
  doneSteps: Record<string, boolean>;
  asks: AskEntry[];
  qHistory?: { q: Question; value: string }[]; // questions answered in this session, for Back/Forward
  demo?: boolean; // the saved sample person is shown, not this person's situation
  added: Partial<Record<StepAnchor, AddedItem[]>>;
  opp?: Partial<OpportunitiesResponse>;
  oppFor?: string; // the facts the opportunities were found for
  savedId?: string; // set when this roadmap came from (or was saved to) the saved list
};

const KEY = "what-now-roadmap-v2";
const empty = (): Saved => ({
  started: false, facts: {}, built: false, tab: "roadmap", doneSteps: {}, asks: [], added: {},
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
  { id: "roadmap", label: "Steps" },
  { id: "opportunities", label: "Opportunities" },
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
  const [focus, setFocus] = useState<{ id: StepAnchor; at: number } | null>(null);
  const [updatingFrom, setUpdatingFrom] = useState<number | null>(null);
  const [stepMsg, setStepMsg] = useState<{ n: number; text: string } | null>(null);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [viewing, setViewing] = useState<number | null>(null); // index in qHistory when gone back; null = current question
  const [saved, setSaved] = useState<SavedRoadmap<Saved>[]>([]);
  useEffect(() => { setSaved(listSaved<Saved>()); }, []);
  const stripRef = useRef<HTMLDivElement>(null);
  const sideRef = useRef<HTMLDivElement>(null); // the checklist beside the steps

  useEffect(() => {
    const fromUrl = new URLSearchParams(window.location.search).get("tab") as Tab | null;
    const state = load();
    setS(fromUrl && TABS.some((t) => t.id === fromUrl) ? { ...state, tab: fromUrl } : state);
    setLoaded(true);
    // Back/forward buttons move between tabs like pages.
    const onPop = () => {
      const t = (new URLSearchParams(window.location.search).get("tab") ?? "roadmap") as Tab;
      setS((prev) => ({ ...prev, tab: TABS.some((x) => x.id === t) ? t : "roadmap" }));
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  /** Each tab has its own address (/start, /start?tab=opportunities, /start?tab=how): refresh, back and links work. */
  const tabHref = (t: Tab) => (t === "roadmap" ? "/start" : `/start?tab=${t}`);
  function goTab(t: Tab) {
    setS((prev) => ({ ...prev, tab: t }));
    if (window.location.pathname + window.location.search !== tabHref(t)) window.history.pushState(null, "", tabHref(t));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
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
    if (e.type === "partial" && (e.key === "deadline" || e.key === "plan")) update({ [e.key]: e.data } as Partial<Saved>);
  }

  async function send(req: Partial<ChatRequest>) {
    setBusy(true);
    setError(null);
    setSearching({});
    try {
      const res = await chatStream({ messages: [], facts: s.facts, step: "this_week", ...req }, onEvent);
      setQVersion((v) => v + 1);
      update({ demo: !!res.demo });
      if (res.out_of_scope) {
        update({ facts: res.facts, outOfScope: { message: res.reply, link: res.link, links: res.links }, question: undefined });
      } else if (res.question) {
        update({ facts: res.facts, question: res.question, outOfScope: undefined });
      } else {
        update({
          facts: res.facts, question: undefined, outOfScope: undefined, built: true,
          deadline: res.deadline, plan: res.plan ?? s.plan,
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

  const [oppLoading, setOppLoading] = useState(false);
  const factsKey = JSON.stringify(["perks-v4", s.facts.city, s.facts.field, s.facts.permit_type, s.facts.years_on_work_permit, s.facts.job_end_date]);

  // Opportunities load once per situation, when the tab is first opened (results are cached server-side too).
  useEffect(() => {
    if (!loaded || s.tab !== "opportunities" || !s.built || !s.facts.city || oppLoading || s.oppFor === factsKey) return;
    setOppLoading(true);
    setSearching({});
    update({ opp: {}, oppFor: factsKey });
    opportunitiesStream(s.facts, (e) => {
      const line = toLogLine(e);
      if (line) setLog((cur) => [...cur, line].slice(-60));
      if (e.type === "partial") setS((prev) => ({ ...prev, opp: { ...prev.opp, [e.key]: e.data } }));
    })
      .then((res) => update({ opp: res }))
      .catch(() => setError("Couldn't load opportunities right now. Please try again in a moment."))
      .finally(() => setOppLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, s.tab, s.built, factsKey]);

  /** Add info to step n: that step and the ones after it are rewritten live; earlier steps stay. */
  async function addInfo(n: number, note: string) {
    if (!s.plan) return;
    setUpdatingFrom(n);
    setStepMsg(null);
    setError(null);
    setSearching({});
    try {
      const res = await stepsUpdateStream({ facts: s.facts, plan: s.plan, step: n, note }, (e) => {
        const line = toLogLine(e);
        if (line) setLog((cur) => [...cur, line].slice(-60));
      });
      // Nothing changes yet: show the current and the new steps side by side, and let the person choose.
      setProposal({ n, note, plan: res.plan, facts: res.facts, factsUpdate: res.facts_update ?? {}, mock: res.mock, message: res.message });
    } catch {
      setError("Couldn't update your steps right now. Please try again in a moment.");
    } finally {
      setUpdatingFrom(null);
    }
  }

  function clearAll() {
    setViewing(null);
    setProposal(null);
    try { window.sessionStorage.removeItem(KEY); } catch {}
    window.history.replaceState(null, "", "/start");
    setS(empty());
    setSearching({});
    setLog([]);
    setConfirmClear(false);
    setError(null);
  }

  function pickExactDate() {
    setEditing("job_end_date");
    (sideRef.current ?? stripRef.current)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  if (!loaded) return null;

  if (!s.started)
    return (
      <main id="main" className="mx-auto max-w-7xl px-5 sm:px-8">
        <Welcome busy={busy} onSubmit={(text) => { update({ started: true }); send({ messages: [{ role: "user", text }] }); }}
          onStart={() => { update({ started: true }); send({}); }}
          saved={saved} phrases={HEADLINE_PHRASES}
          onOpen={(id) => { const r = saved.find((x) => x.id === id); if (r) setS({ ...empty(), ...r.state, savedId: r.id }); }}
          onDelete={(id) => { deleteSaved(id); setSaved(listSaved<Saved>()); }} />
      </main>
    );

  const phase = s.built ? "roadmap" : finding ? "finding" : "tell";
  const askingQuestion = !s.outOfScope && !s.built && !finding && !!s.question;
  const editFact = (field: Field, value: Facts[Field]) => send({ edited_facts: { [field]: value } as Partial<Facts> });
  const tab: Tab = (TABS.some((t) => t.id === s.tab) ? s.tab : "roadmap") as Tab;

  // Ask lives on the Steps tab (the Opportunities tab links to it).
  const ask = (
    <AskPanel facts={s.facts} entries={s.asks}
      onEntry={(e) => {
        update({ asks: [...s.asks, e] });
        if (e.res.facts_update && Object.keys(e.res.facts_update).length) {
          goTab("roadmap");
          send({ edited_facts: e.res.facts_update });
        }
      }}
      onAdd={(i) => {
        const e = s.asks[i];
        const suggested = e.res.suggested_roadmap_step!;
        const step: StepAnchor = suggested === "deadline" || suggested === "final" ? "deadline" : "week1";
        goTab("roadmap");
        update({
          asks: s.asks.map((x, k) => (k === i ? { ...x, added: true } : x)),
          added: { ...s.added, [step]: [...(s.added[step] ?? []), { question: e.question, answer: e.res.answer, sources: e.res.sources }] },
        });
        setFocus({ id: step, at: Date.now() });
      }} />
  );

  const roadmapTitle = () => {
    const permit = display(FIELDS.find((f) => f.id === "permit_type")!, s.facts.permit_type) ?? "My situation";
    const when = s.deadline?.deadline_date
      ? new Date(s.deadline.deadline_date + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })
      : null;
    return [permit, s.facts.city, when && `stay until ${when}`].filter(Boolean).join(" · ");
  };
  const newSituation = (
    <div className="flex min-w-0 max-w-full flex-wrap items-center gap-2">
      {confirmClear ? (
        <>
          <span className="text-sm">Start a new situation. Keep this one?</span>
          {s.built && (
            <Button variant="chip" onClick={() => {
              const summary = FIELDS.map((f) => display(f, s.facts[f.id], s.facts)).filter((t): t is string => !!t);
              saveRoadmap(roadmapTitle(), summary, s, s.savedId);
              setSaved(listSaved<Saved>());
              clearAll();
            }}>
              {s.savedId ? "Save changes" : "Save these steps"}
            </Button>
          )}
          <Button variant="chip" onClick={clearAll}>Discard</Button>
          <Button variant="quiet" onClick={() => setConfirmClear(false)}>Cancel</Button>
        </>
      ) : (
        <Button variant="chip" onClick={() => setConfirmClear(true)}>+ New situation</Button>
      )}
    </div>
  );
  const opportunitiesHint = s.built && s.tab === "roadmap" && (
    <button onClick={() => goTab("opportunities")}
      className="flex w-full items-center justify-between gap-3 rounded-2xl border border-accent/40 bg-accent-soft px-5 py-4 text-left font-bold text-accent-ink hover:border-accent">
      Next: perks and support for jobseekers <span aria-hidden>→</span>
    </button>
  );
  const live = !!s.plan && !s.plan.mock;

  return (
    <main id="main" className="mx-auto max-w-6xl space-y-8 px-5 pb-16 pt-8 sm:px-8 sm:pt-10">
      {/* Row 1: setup progress, or tabs once the roadmap exists; "New situation" is always here */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        {s.built ? (
          <nav aria-label="Your sections" className="min-w-0 flex-1 border-b border-rule">
            <ul className="-mb-px flex flex-wrap gap-1 sm:gap-2">
              {TABS.map((t) => {
                const current = tab === t.id;
                const count = t.id === "opportunities" ? s.opp?.counts?.total : undefined;
                return (
                  <li key={t.id}>
                    <a href={tabHref(t.id)} aria-current={current ? "page" : undefined}
                      onClick={(e) => { if (e.metaKey || e.ctrlKey || e.shiftKey) return; e.preventDefault(); goTab(t.id); }}
                      className={cx("inline-flex min-h-12 items-center gap-2 rounded-t-xl border-b-[3px] px-4 font-bold transition-colors",
                        current ? "border-ink bg-card text-ink" : "border-transparent text-ink-soft hover:bg-paper-deep hover:text-ink")}>
                      {t.label}
                      {!!count && (
                        <span className="inline-flex min-w-6 items-center justify-center rounded-full bg-accent-soft px-2 py-0.5 text-sm text-accent-ink">
                          {count}<span className="sr-only"> items</span>
                        </span>
                      )}
                    </a>
                  </li>
                );
              })}
            </ul>
          </nav>
        ) : (
          <FlowProgress phase={phase} />
        )}
        {newSituation}
      </div>

      {/* Demo mode: say plainly that this is a sample person, so nobody mistakes it for their own situation */}
      {(s.demo || (tab === "opportunities" && s.opp?.demo)) && (
        <div role="note" className="rounded-2xl border-2 border-accent/60 bg-accent-soft px-5 py-4 text-accent-ink">
          <p className="font-bold">Demo with a sample person, not your situation</p>
          <p className="mt-1">
            Live checks are off, so you&apos;re seeing a saved example (a restaurant worker in Helsinki on a work permit).
            Your own answers aren&apos;t used for these steps or perks.
          </p>
        </div>
      )}

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
            <p className="text-ink-soft">Got something wrong? Edit a detail below, or start over.</p>
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
                {(() => {
                  const history = s.qHistory ?? [];
                  const past = viewing !== null ? history[viewing] : undefined;
                  // Answering (or re-answering) question q: remember it, drop anything answered after it, and send.
                  const answer = (q: Question, value: string, keep: number, text = false) => {
                    setViewing(null);
                    update({ qHistory: [...history.slice(0, keep), { q, value }] });
                    send(text ? { messages: [{ role: "user", text: value }] } : { answers: { [q.id]: value } as Partial<Facts> });
                  };
                  if (past && viewing !== null)
                    return (
                      <QuestionCard key={`past-${viewing}-${past.q.id}`} question={past.q} busy={busy} previous={past.value}
                        position={`Question ${viewing + 1}`}
                        onBack={viewing > 0 ? () => setViewing(viewing - 1) : undefined}
                        onForward={() => setViewing(viewing + 1 < history.length ? viewing + 1 : null)}
                        onAnswer={(value) => value === past.value
                          ? setViewing(viewing + 1 < history.length ? viewing + 1 : null)  // same answer: just move on
                          : answer(past.q, value, viewing)}
                        onText={(t) => answer(past.q, t, viewing, true)} />
                    );
                  return (
                    <QuestionCard key={`${s.question!.id}-${qVersion}`} question={s.question!} busy={busy}
                      position={`Question ${history.length + 1}`}
                      onBack={history.length ? () => setViewing(history.length - 1) : undefined}
                      onAnswer={(value) => answer(s.question!, value, history.length)}
                      onText={(t) => answer(s.question!, t, history.length, true)} />
                  );
                })()}
                <ActivityLog lines={log} busy={busy} last={3} />
              </div>
              <Checklist facts={s.facts} open={editing} onOpen={setEditing} onEdit={editFact} />
            </div>
          ) : (
            <div className="mx-auto max-w-3xl space-y-4">
              <p className="font-serif text-2xl">Reading your situation…</p>
              <ActivityLog lines={log} busy={busy} last={3} />
            </div>
          )
        ) : (
          <div className="space-y-6">
            <div id={`panel-${tab}`}>
              {tab === "roadmap" && (
                <div className="grid items-start gap-6 md:grid-cols-[minmax(0,1fr)_17rem] lg:grid-cols-[minmax(0,1fr)_20rem]">
                <div className="min-w-0 space-y-6">
                  <div>
                    <h2 className="font-serif text-3xl font-semibold sm:text-4xl">Your steps</h2>
                    <p className="mt-2 text-lg text-ink-soft">
                      {busy ? "Updating with your change…"
                        : live ? "In order, found live today. Add info to any step and it updates, with the steps after it."
                        : "Live data isn't available right now, so these steps use our checked saved guide."}
                    </p>
                  </div>
                  {ask}
                  {(busy || updatingFrom !== null) && <ActivityLog lines={log} busy last={3} />}
                  <Steps
                    plan={s.plan}
                    deadline={s.deadline}
                    live={live}
                    done={s.doneSteps ?? {}}
                    added={s.added}
                    updatingFrom={updatingFrom}
                    message={stepMsg}
                    searchingText={updatingFrom !== null ? log.at(-1)?.text : undefined}
                    onToggleDone={(key) => update({ doneSteps: { ...s.doneSteps, [key]: !s.doneSteps?.[key] } })}
                    onAddInfo={addInfo}
                    onPickExactDate={pickExactDate}
                    focus={focus}
                    proposal={proposal}
                    onAccept={() => {
                      if (!proposal) return;
                      update({ plan: proposal.plan, deadline: proposal.plan.deadline, facts: proposal.facts });
                      const key = (p?: PlanResponse) => JSON.stringify(flattenSteps(p).map((x) => [x.title, x.why ?? "", x.points]));
                      const changed = !proposal.mock && key(proposal.plan) !== key(s.plan);
                      setStepMsg({ n: proposal.n, text: changed ? "Updated with what you added." : "Saved what you added. Your steps stay the same." });
                      setProposal(null);
                    }}
                    onDiscard={() => { if (proposal) setStepMsg({ n: proposal.n, text: "Kept your current steps." }); setProposal(null); }}
                  />
                  {opportunitiesHint}
                  <Legend />
                </div>
                {/* What we know so far: on the right of the steps (below them on small screens) */}
                <div ref={sideRef} className="scroll-mt-24 md:sticky md:top-6">
                  <Checklist facts={s.facts} open={editing} onOpen={setEditing} onEdit={editFact} />
                </div>
                </div>
              )}
              {tab === "opportunities" && (
                <div className="space-y-6">
                  {!s.facts.city ? (
                    <section className="rounded-2xl border border-rule bg-card px-5 py-5">
                      <h2 className="font-serif text-3xl font-semibold">Perks and support where you live</h2>
                      <p className="mt-2 text-ink-soft">Discounts and support depend on your city. Add it here when you want to explore this tab.</p>
                      <div className="mt-4">
                        <Button variant="chip" onClick={() => { setEditing("city"); stripRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }); }}>Add city</Button>
                      </div>
                    </section>
                  ) : (
                    <>
                      {oppLoading && <ActivityLog lines={log} busy last={3} />}
                      <Opportunities data={s.opp ?? {}} loading={oppLoading} />
                    </>
                  )}
                  {/* Ask lives on the Steps tab only; this just takes you there. */}
                  <p className="border-t border-rule pt-4 text-ink-soft">
                    Have a question about a perk?{" "}
                    <button className="min-h-9 font-bold text-ink underline"
                      onClick={() => { goTab("roadmap"); setTimeout(() => document.getElementById("ask-input")?.focus(), 150); }}>
                      Ask on the Steps tab →
                    </button>
                  </p>
                </div>
              )}
              {tab === "how" && <HowWeKnow embedded />}
            </div>
          </div>
        )}
      </div>

      {/* Row 3: what we know so far, editable (beside the question instead while questions are being asked) */}
      <div ref={stripRef} className="space-y-3">
        {!askingQuestion && !(s.built && tab === "roadmap") && (
          <Checklist facts={s.facts} open={editing} onOpen={setEditing} onEdit={editFact} wide
            also={s.built && tab === "opportunities" ? ["city"] : []} />
        )}
        {error && <GentleWarning>{error}</GentleWarning>}
      </div>
    </main>
  );
}
