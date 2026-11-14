"use client";

import { useRef, useState } from "react";
import type { OpportunitiesResponse } from "@/lib/api";
import { isSample } from "@/lib/format";
import { GlobeIcon } from "./icons";
import { Button, SourceChip, cx } from "./primitives";
import { ListenButton } from "./Voice";
import { ExpandAll } from "./ExpandAll";

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
    <span className="group/readby relative inline-flex">
      <span tabIndex={0}
        className="inline-flex min-h-9 items-center gap-1.5 rounded-full border border-ink/20 bg-card px-3 py-1 text-sm font-bold text-ink">
        <span aria-hidden>▤</span> Read from the page by Context.dev<span className="sr-only">. {why}</span>
      </span>
      <span role="tooltip" aria-hidden className="pointer-events-none absolute bottom-full left-0 z-20 mb-2 hidden w-[min(20rem,80vw)] rounded-xl border border-rule bg-card p-3 text-sm font-normal shadow-lg group-hover/readby:block group-focus-within/readby:block">
        {why}
      </span>
    </span>
  );
}

function Src({ url, title, date }: { url: string; title: string; date?: string | null }) {
  return <SourceChip live={!isSample(url)} source={{ title, url, published: date }} />;
}

/** One topic as a quiet, collapsible row: title and a short hint, details inside. */
function Topic({ title, hint, open, empty, searching, reason, children }: {
  title: string; hint: string; open: boolean; empty: boolean; searching: boolean; reason?: string; children: React.ReactNode;
}) {
  return (
    <details open={open} className="group border-b border-rule last:border-b-0">
      <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-4 py-4 [&::-webkit-details-marker]:hidden">
        <span className="min-w-0">
          <span className="block font-serif text-xl font-semibold">{title}</span>
          <span className="block truncate text-ink-soft group-open:hidden">
            {empty && searching ? <><GlobeIcon className="mr-1 inline h-4 w-4 text-verified motion-safe:animate-pulse" />Searching live…</> : hint}
          </span>
        </span>
        <svg aria-hidden viewBox="0 0 20 20" className="h-5 w-5 shrink-0 text-ink-soft transition-transform group-open:rotate-180">
          <path d="M5 7.5l5 5 5-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </summary>
      <div className="space-y-4 pb-5">
        {empty ? <p className="text-ink-soft">{searching ? "Searching live…" : "Nothing we could confirm with a source right now."}</p> : children}
        {reason && <p className="text-sm text-ink-soft">Why you see this: {reason}</p>}
      </div>
    </details>
  );
}

/** One item: name, a line or two, then its sources. No boxes, just spacing. */
function Item({ name, listen, children, src }: { name: string; listen: string; children: React.ReactNode; src: React.ReactNode }) {
  return (
    <li className="space-y-1">
      <div className="flex items-start justify-between gap-3">
        <p className="font-bold">{name}</p>
        <ListenButton iconOnly what={name} text={listen} />
      </div>
      {children}
      <div className="flex flex-wrap gap-2 pt-1">{src}</div>
    </li>
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
  const list = useRef<HTMLDivElement>(null);

  /** General items for a topic: support found live, or the saved guide when there's no live search. */
  function supportList(id: string) {
    const list = (perks?.support ?? []).filter((x) => x.topic === id);
    return list.length ? (
      <ul className="space-y-4">
        {list.map((x, i) => (
          <Item key={i} name={x.name}
            listen={[x.name + ".", x.what_it_is, x.who_can_get_it && `Who can get it: ${x.who_can_get_it}.`, x.how_to_get && `How: ${x.how_to_get}`].filter(Boolean).join(" ")}
            src={<><Src url={x.source_url} title="Official page" date={x.source_date} /><ReadBy by={x.read_by} /></>}>
            <p>{x.what_it_is}</p>
            {x.who_can_get_it && <p className="text-sm text-ink-soft">Who can get it: {x.who_can_get_it}</p>}
            {x.how_to_get && <p className="text-sm text-ink-soft">How: {x.how_to_get}</p>}
          </Item>
        ))}
      </ul>
    ) : null;
  }

  /** Items for one topic. Nothing is shown unless a page confirms it (or it's the saved guide, labelled as such). */
  function items(id: string) {
    const c = perks?.certificate;
    if (id === "certificate")
      return c ? (
        <ul><Item name="How to get it" listen={`${c.name}. ${c.how_to_get}`}
          src={<><Src url={c.source_url} title="How to get it" date={c.source_date} /><ReadBy by={c.read_by} /></>}>
          <p>{c.how_to_get}</p>
        </Item></ul>
      ) : supportList(id);
    if (id === "discounts")
      return discounts.shown.length ? (
        <ul className="space-y-4">
          {discounts.shown.map((d, i) => (
            <Item key={i} name={d.name} listen={`${d.name}: ${d.discount}. Proof needed: ${d.proof_needed}.`}
              src={<><Src url={d.source_url} title={d.city} date={d.source_date} /><ReadBy by={d.read_by} /></>}>
              <p>{d.discount}</p>
              <p className="text-sm text-ink-soft">Proof needed: {d.proof_needed}</p>
            </Item>
          ))}
          <More {...discounts} />
        </ul>
      ) : supportList(id);
    if (id === "incentives")
      return perks?.incentives.length ? (
        <ul className="space-y-4">
          {perks.incentives.map((inc, i) => (
            <Item key={i} name={inc.name} listen={`${inc.name}. ${inc.what_it_is} Conditions: ${inc.conditions_plain}. ${inc.caveat}`}
              src={<><Src url={inc.source_url} title="Conditions" date={inc.source_date} /><ReadBy by={inc.read_by} /></>}>
              <p>{inc.what_it_is}</p>
              <p className="text-sm text-ink-soft">Conditions: {inc.conditions_plain}</p>
              <p className={cx("text-sm font-bold", inc.may_apply ? "text-verified" : "text-warn")}>
                {/^may apply/i.test(inc.caveat) ? "" : inc.may_apply ? "May apply to you. " : "Probably doesn't apply right now. "}{inc.caveat}
              </p>
            </Item>
          ))}
        </ul>
      ) : supportList(id);
    return supportList(id);
  }

  /** The short line under a closed topic: the first thing in it. */
  function hint(id: string, label: string) {
    if (id === "certificate") return label; // the topic title already says "Job search certificate"
    if (id === "discounts") return perks?.discounts[0] ? `${perks.discounts[0].name} · ${perks.discounts[0].discount}` : label;
    if (id === "incentives") return perks?.incentives[0]?.name ?? label;
    return (perks?.support ?? []).find((x) => x.topic === id)?.name ?? label;
  }

  const shown = topics.filter((t, i) => items(t.id) || loading || i < 3); // extra topics only when a page confirms something

  return (
    <section aria-labelledby="opp-title" className="space-y-4">
      <div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="opp-title" className="font-serif text-3xl font-semibold sm:text-4xl">Perks and support</h2>
          <ExpandAll target={list} />
        </div>
        <p className="mt-2 text-ink-soft">
          {data.mock && !loading
            ? "From our saved guide: general pointers, each linking to the official page. They weren't checked live, so open the page for the details that apply to you."
            : "Found live on official and city sites. Open a topic for details and sources."}
        </p>
      </div>

      <div ref={list} className="rounded-2xl border border-rule bg-card px-5 sm:px-7">
        {shown.length === 0 ? (
          <Topic title="Perks and support" hint="Proof you're a jobseeker, discounts, and help for employers who hire you."
            open empty searching={loading}><span /></Topic>
        ) : shown.map((t, i) => {
          const body = items(t.id);
          return (
            <Topic key={t.id} title={t.title} hint={hint(t.id, t.label)} open={i === 0} empty={!body}
              searching={loading} reason={t.reason}>
              {body}
            </Topic>
          );
        })}
      </div>

    </section>
  );
}
