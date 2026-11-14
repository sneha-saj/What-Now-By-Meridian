"use client";

import { useState } from "react";
import type { OpportunitiesResponse } from "@/lib/api";
import { isSample } from "@/lib/format";
import { GlobeIcon } from "./icons";
import { Button, Card, SourceChip, cx } from "./primitives";

const SHOW = 3;

function useMore<T>(items: T[]) {
  const [all, setAll] = useState(false);
  return { shown: all ? items : items.slice(0, SHOW), more: items.length - SHOW, all, toggle: () => setAll(!all) };
}

function More({ more, all, toggle }: { more: number; all: boolean; toggle: () => void }) {
  return more > 0 ? <Button variant="quiet" onClick={toggle}>{all ? "Show fewer" : `Show ${more} more`}</Button> : null;
}

/** Shown on items whose details Context.dev read from the page itself, with why that matters. */
function ReadBy({ by }: { by?: "context.dev" | null }) {
  if (by !== "context.dev") return null;
  const why = "Context.dev opened this official page and pulled out these exact details, so they're the page's own words, not a search snippet.";
  return (
    <span className="group relative inline-flex">
      <span tabIndex={0} title={why}
        className="inline-flex min-h-9 items-center gap-1.5 rounded-full border border-ink/20 bg-card px-3 py-1 text-sm font-bold text-ink">
        <span aria-hidden>▤</span> Read from the page by Context.dev<span className="sr-only">. {why}</span>
      </span>
      <span role="tooltip" aria-hidden className="pointer-events-none absolute bottom-full left-0 z-20 mb-2 hidden w-[min(20rem,80vw)] rounded-xl border border-rule bg-card p-3 text-sm font-normal shadow-lg group-hover:block group-focus-within:block">
        {why}
      </span>
    </span>
  );
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

export function Opportunities({
  data, loading,
}: {
  data: Partial<OpportunitiesResponse>;
  loading: boolean;
}) {
  const perks = data.perks_and_support;
  const discounts = useMore(perks?.discounts ?? []);
  const topics = perks?.topics ?? [];

  /** Items for one topic, in the same card style. Nothing is shown unless a page confirms it. */
  function items(id: string) {
    if (id === "certificate")
      return perks?.certificate ? (
        <div className="rounded-2xl border border-verified/30 bg-verified-soft/50 p-4">
          <p className="font-bold">Start here: {perks.certificate.name}</p>
          <p className="mt-1">{perks.certificate.how_to_get}</p>
          <div className="mt-2 flex flex-wrap gap-2"><Src url={perks.certificate.source_url} title="How to get it" date={perks.certificate.source_date} /><ReadBy by={perks.certificate.read_by} /></div>
        </div>
      ) : null;
    if (id === "discounts")
      return discounts.shown.length ? (
        <ul className="space-y-3">
          {discounts.shown.map((d, i) => (
            <li key={i}>
              <p><strong>{d.name}</strong> · {d.discount}</p>
              <p className="text-sm text-ink-soft">Proof needed: {d.proof_needed}</p>
              <div className="mt-1 flex flex-wrap gap-2"><Src url={d.source_url} title={d.city} date={d.source_date} /><ReadBy by={d.read_by} /></div>
            </li>
          ))}
          <More {...discounts} />
        </ul>
      ) : null;
    if (id === "incentives")
      return perks?.incentives.length ? (
        <div className="space-y-3">
          {perks.incentives.map((inc, i) => (
            <div key={i} className="rounded-2xl border border-rule bg-paper p-4">
              <p className="font-bold">{inc.name}</p>
              <p className="mt-1">{inc.what_it_is}</p>
              <p className="mt-1"><span className="text-ink-soft">Conditions: </span>{inc.conditions_plain}</p>
              <p className={cx("mt-2 rounded-lg px-3 py-2", inc.may_apply ? "bg-verified-soft text-verified" : "bg-warn-soft text-warn")}>
                {/^may apply/i.test(inc.caveat) ? "" : inc.may_apply ? "May apply to you. " : "Probably doesn't apply right now. "}{inc.caveat}
              </p>
              <p className="mt-2 text-sm text-ink-soft">You can mention this to an employer when you apply.</p>
              <div className="mt-2 flex flex-wrap gap-2"><Src url={inc.source_url} title="Conditions" date={inc.source_date} /><ReadBy by={inc.read_by} /></div>
            </div>
          ))}
        </div>
      ) : null;
    const list = (perks?.support ?? []).filter((x) => x.topic === id);
    return list.length ? (
      <ul className="space-y-3">
        {list.map((x, i) => (
          <li key={i} className="rounded-2xl border border-rule bg-paper p-4">
            <p className="font-bold">{x.name}</p>
            <p className="mt-1">{x.what_it_is}</p>
            {x.who_can_get_it && <p className="mt-1"><span className="text-ink-soft">Who can get it: </span>{x.who_can_get_it}</p>}
            {x.how_to_get && <p className="mt-1"><span className="text-ink-soft">How: </span>{x.how_to_get}</p>}
            <div className="mt-2 flex flex-wrap gap-2"><Src url={x.source_url} title="Official page" date={x.source_date} /><ReadBy by={x.read_by} /></div>
          </li>
        ))}
      </ul>
    ) : null;
  }

  return (
    <section aria-labelledby="opp-title" className="space-y-6">
      <div>
        <h2 id="opp-title" className="font-serif text-3xl font-semibold sm:text-4xl">Perks and support</h2>
        <p className="mt-2 text-lg text-ink-soft">
          Picked for your situation, found live on official and city sites. Every item links to where it came from, with the page date.
        </p>
      </div>

      {topics.length === 0 && (
        <Section title="Perks and support" intro="Proof you're a jobseeker, discounts, and help employers can get for hiring you."
          empty searching={loading}><span /></Section>
      )}
      {topics.map((t, i) => {
        const body = items(t.id);
        if (!body && !loading && i >= 3) return null; // extra topics show only when a page confirms something
        return (
          <Section key={t.id} title={t.title} intro={t.label} empty={!body} searching={loading}>
            {body}
          </Section>
        );
      })}
      {topics.length > 0 && (
        <details className="text-sm text-ink-soft">
          <summary className="min-h-9 cursor-pointer font-bold text-ink">Why you see these</summary>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {topics.map((t) => <li key={t.id}><strong className="text-ink">{t.title}:</strong> {t.reason}</li>)}
          </ul>
        </details>
      )}

      {data.mock && !loading && (
        <p className="text-sm text-ink-soft">Some of this couldn&apos;t be checked live right now, so this may be empty.</p>
      )}
    </section>
  );
}
