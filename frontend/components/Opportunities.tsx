"use client";

import { useState } from "react";
import type { OpportunitiesResponse, OppContact } from "@/lib/api";
import { isSample } from "@/lib/format";
import { GlobeIcon } from "./icons";
import { Button, Card, SourceChip, cx, formatDate } from "./primitives";

const SHOW = 3;

function useMore<T>(items: T[]) {
  const [all, setAll] = useState(false);
  return { shown: all ? items : items.slice(0, SHOW), more: items.length - SHOW, all, toggle: () => setAll(!all) };
}

function More({ more, all, toggle }: { more: number; all: boolean; toggle: () => void }) {
  return more > 0 ? <Button variant="quiet" onClick={toggle}>{all ? "Show fewer" : `Show ${more} more`}</Button> : null;
}

function Src({ url, title, date }: { url: string; title: string; date?: string | null }) {
  return <SourceChip live={!isSample(url)} source={{ title, url, published: date }} />;
}

function Section({ title, intro, empty, searching, children }: {
  title: string; intro: string; empty: boolean; searching: boolean; children: React.ReactNode;
}) {
  return (
    <Card title={title}>
      <p className="-mt-2 mb-4 text-ink-soft">{intro}</p>
      {empty ? (
        <p className="flex items-center gap-2 text-ink-soft">
          {searching ? <><GlobeIcon className="h-4 w-4 text-verified motion-safe:animate-pulse" /> Searching live…</>
            : "Nothing we could confirm with a source right now."}
        </p>
      ) : children}
    </Card>
  );
}

function PersonCard({ p, text, onText }: { p: OppContact; text: string; onText: (t: string) => void }) {
  const [copied, setCopied] = useState(false);
  const id = `opp-draft-${p.profile_url}`;
  return (
    <li className="rounded-2xl border border-rule bg-paper p-4">
      <p className="font-serif text-xl font-semibold">{p.name}</p>
      <p className="text-ink-soft">{p.role} · {p.company}</p>
      <p className="mt-1"><span className="text-ink-soft">Why this person: </span>{p.why_this_person}</p>
      <div className="mt-2"><Src url={p.profile_url} title="Public profile" /></div>
      <label htmlFor={id} className="mt-3 block font-bold">Your draft message</label>
      <p className="text-sm text-ink-soft">Edit it so it sounds like you. Nothing is sent: copy it and send it yourself.</p>
      <textarea id={id} rows={5} value={text} onChange={(e) => { onText(e.target.value); setCopied(false); }}
        className="mt-2 w-full rounded-xl border border-ink/25 bg-card p-3" />
      <div className="mt-2 flex items-center gap-3">
        <Button variant="chip" onClick={async () => { try { await navigator.clipboard.writeText(text); setCopied(true); } catch {} }}>
          {copied ? "Copied ✓" : "Copy message"}
        </Button>
        <span aria-live="polite" className="sr-only">{copied ? "Copied to clipboard" : ""}</span>
        <span className="text-sm text-ink-soft">{text.trim().split(/\s+/).length} words</span>
      </div>
    </li>
  );
}

export function Opportunities({
  data, loading, drafts, onDraft,
}: {
  data: Partial<OpportunitiesResponse>;
  loading: boolean;
  drafts: Record<string, string>;
  onDraft: (url: string, text: string) => void;
}) {
  const jobs = useMore(data.hidden_jobs ?? []);
  const people = useMore(data.people ?? []);
  const support = useMore(data.support ?? []);
  const events = useMore(data.events ?? []);
  const perks = data.perks_and_support;
  const perkItems = [...(perks?.discounts ?? [])];
  const discounts = useMore(perkItems);

  return (
    <section aria-labelledby="opp-title" className="space-y-6">
      <div>
        <h2 id="opp-title" className="font-serif text-3xl font-semibold sm:text-4xl">Opportunities</h2>
        <p className="mt-2 text-lg text-ink-soft">
          Found live by Exa for your city and work. Every item links to where it came from.
        </p>
      </div>

      <Section title="Hidden jobs" intro="Companies that just opened, expanded or raised money: they're likely hiring before they advertise."
        empty={!jobs.shown.length} searching={loading}>
        <ul className="space-y-4">
          {jobs.shown.map((j, i) => (
            <li key={i} className="border-b border-rule pb-4 last:border-0 last:pb-0">
              <p className="font-serif text-xl font-semibold">{j.company}</p>
              <p className="mt-1"><GlobeIcon className="mr-1.5 h-4 w-4 text-verified" />{j.signal}
                <span className="text-ink-soft"> · {formatDate(j.signal_date)}</span></p>
              <p className="mt-1 text-ink-soft">{j.why_it_fits}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Src url={j.source_url} title="News" date={j.signal_date} />
                <span className="rounded-full bg-accent-soft px-2.5 py-0.5 text-sm font-bold text-accent-ink">Reach out</span>
              </div>
            </li>
          ))}
        </ul>
        <div className="mt-3"><More {...jobs} /></div>
      </Section>

      <Section title="People who could refer you" intro="Public professional profiles at those companies, with a short draft you can edit and send yourself."
        empty={!people.shown.length} searching={loading}>
        <ul className="space-y-4">
          {people.shown.map((p) => (
            <PersonCard key={p.profile_url} p={p} text={drafts[p.profile_url] ?? p.draft} onText={(t) => onDraft(p.profile_url, t)} />
          ))}
        </ul>
        <div className="mt-3"><More {...people} /></div>
      </Section>

      <Section title="Perks and support" intro="Proof you're a jobseeker, discounts, and help employers can get for hiring you."
        empty={!perks?.certificate && !perkItems.length && !perks?.incentives.length} searching={loading}>
        <div className="space-y-5">
          {perks?.certificate && (
            <div className="rounded-2xl border border-verified/30 bg-verified-soft/50 p-4">
              <p className="font-bold">Start here: {perks.certificate.name}</p>
              <p className="mt-1">{perks.certificate.how_to_get}</p>
              <div className="mt-2"><Src url={perks.certificate.source_url} title="How to get it" date={perks.certificate.source_date} /></div>
            </div>
          )}
          {discounts.shown.length > 0 && (
            <ul className="space-y-3">
              {discounts.shown.map((d, i) => (
                <li key={i}>
                  <p><strong>{d.name}</strong> · {d.discount}</p>
                  <p className="text-sm text-ink-soft">Proof needed: {d.proof_needed}</p>
                  <div className="mt-1"><Src url={d.source_url} title={d.city} date={d.source_date} /></div>
                </li>
              ))}
              <More {...discounts} />
            </ul>
          )}
          {perks?.incentives.map((inc, i) => (
            <div key={i} className="rounded-2xl border border-rule bg-paper p-4">
              <p className="font-bold">{inc.name}</p>
              <p className="mt-1">{inc.what_it_is}</p>
              <p className="mt-1"><span className="text-ink-soft">Conditions: </span>{inc.conditions_plain}</p>
              <p className={cx("mt-2 rounded-lg px-3 py-2", inc.may_apply ? "bg-verified-soft text-verified" : "bg-warn-soft text-warn")}>
                {inc.may_apply ? "May apply to you. " : "Probably doesn't apply right now. "}{inc.caveat}
              </p>
              <div className="mt-2"><Src url={inc.source_url} title="Conditions" date={inc.source_date} /></div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Support you may be able to get" intro="Courses and programmes whose conditions may fit you. Always check the conditions."
        empty={!support.shown.length} searching={loading}>
        <ul className="space-y-4">
          {support.shown.map((s, i) => (
            <li key={i}>
              <p className="font-bold">{s.name}</p>
              <p className="mt-1">{s.what_it_is}</p>
              <p className="mt-1 text-ink-soft">{s.why_it_may_apply} {s.eligibility_note}</p>
              <div className="mt-2"><Src url={s.source_url} title="Official page" date={s.source_date} /></div>
            </li>
          ))}
        </ul>
        <div className="mt-3"><More {...support} /></div>
      </Section>

      <Section title="Events in the next 30 days" intro="Recruitment fairs, meetups and community events in your city."
        empty={!events.shown.length} searching={loading}>
        <ul className="space-y-3">
          {events.shown.map((e, i) => (
            <li key={i} className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="font-serif text-lg font-semibold">{formatDate(e.date)}</span>
              <a href={e.url} target="_blank" rel="noreferrer" className="font-bold underline decoration-rule underline-offset-4 hover:decoration-ink">
                {e.name}<span className="sr-only"> (opens in a new tab)</span>
              </a>
              {e.place && <span className="text-ink-soft">{e.place}</span>}
              <span className="basis-full text-ink-soft">{e.why_relevant}</span>
            </li>
          ))}
        </ul>
        <div className="mt-3"><More {...events} /></div>
      </Section>
      {data.mock && !loading && (
        <p className="text-sm text-ink-soft">Some of this couldn&apos;t be checked live right now, so those sections may be empty.</p>
      )}
    </section>
  );
}
