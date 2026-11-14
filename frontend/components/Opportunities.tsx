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
  const perkItems = [...(perks?.discounts ?? [])];
  const discounts = useMore(perkItems);

  return (
    <section aria-labelledby="opp-title" className="space-y-6">
      <div>
        <h2 id="opp-title" className="font-serif text-3xl font-semibold sm:text-4xl">Opportunities</h2>
        <p className="mt-2 text-lg text-ink-soft">
          Found live by Exa on official and city sites for where you live. Every item links to where it came from, with the page date.
        </p>
      </div>

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

      {data.mock && !loading && (
        <p className="text-sm text-ink-soft">Some of this couldn&apos;t be checked live right now, so this may be empty.</p>
      )}
    </section>
  );
}
