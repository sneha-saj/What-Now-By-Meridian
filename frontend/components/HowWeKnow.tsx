"use client";
// The "How we know this" content, shared by this page and the tab on /start.

import { useEffect, useState, type SyntheticEvent } from "react";
import { api, type RulesResponse } from "@/lib/api";

function groupBy<T>(items: T[], key: (t: T) => string): Record<string, T[]> {
  return items.reduce((acc, t) => ((acc[key(t)] ??= []).push(t), acc), {} as Record<string, T[]>);
}

function checkedTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Time unavailable" : date.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
}

export function HowWeKnow({ embedded = false }: { embedded?: boolean }) {
  const [data, setData] = useState<RulesResponse | null>(null);
  const [error, setError] = useState(false);
  const [loadLive, setLoadLive] = useState(false);
  useEffect(() => {
    if (loadLive) api.rules().then(setData).catch(() => setError(true));
  }, [loadLive]);
  const load = (event: SyntheticEvent<HTMLDetailsElement>) => {
    if (event.currentTarget.open) setLoadLive(true);
  };
  return (
    <div className={embedded ? "space-y-4" : "mx-auto max-w-3xl space-y-4 px-5 py-10 sm:px-8"}>
      <header className="space-y-2">
        {embedded ? <h2 className="font-serif text-3xl font-semibold">How we know this</h2>
          : <h1 className="font-serif text-4xl font-semibold sm:text-5xl">How we know this</h1>}
        <p className="text-ink-soft">We link to official sources and check key rules daily. Open a section if you want the details.</p>
      </header>
      <details className="group rounded-2xl bg-white shadow-sm ring-1 ring-calm-100" onToggle={load}>
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-2xl px-5 py-4 hover:bg-calm-50 [&::-webkit-details-marker]:hidden">
          <span><span className="block text-lg font-semibold">Permit rules</span><span className="text-sm text-ink-soft">Sources and checks behind the dates we show</span></span>
          <span aria-hidden="true" className="text-xl text-ink-soft group-open:rotate-180">⌄</span>
        </summary>
        <div className="space-y-3 border-t border-calm-100 p-4">
        {error && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">We couldn’t load the latest rule checks. Please check <a href="https://migri.fi/en" target="_blank" rel="noreferrer" className="underline">Migri</a> directly.</p>}
        {!error && <div className="overflow-x-auto rounded-xl ring-1 ring-calm-100">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="bg-calm-50 text-calm-700"><tr>
              <th className="p-3 font-semibold">Rule</th><th className="p-3 font-semibold">What it says</th><th className="p-3 font-semibold">Source</th><th className="p-3 font-semibold">In force since</th><th className="p-3 font-semibold">Live check</th>
            </tr></thead>
            <tbody>{data?.rules.map((rule) => <tr key={rule.id} className="border-t border-calm-100 align-top">
              <td className="p-3 font-medium">{rule.months === null ? "Not applicable" : `${rule.months} months`}</td>
              <td className="p-3 text-calm-700">{rule.description}<p className="mt-1 text-xs text-calm-500">Applies to: {rule.applies_to.join(", ")}</p></td>
              <td className="p-3"><a className="text-calm-700 underline" href={rule.source_url} target="_blank" rel="noreferrer">Migri</a></td>
              <td className="p-3">{rule.in_force_since}</td>
              <td className="p-3"><span className={rule.live_check.status === "verified" ? "font-bold text-verified" : rule.live_check.status === "mismatch" ? "font-bold text-warn" : "text-ink-soft"}>{rule.live_check.status === "verified" ? "✓ Matches Migri today" : rule.live_check.status === "mismatch" ? "May have changed" : "Couldn't check right now"}</span><p className="mt-1 text-xs text-calm-500">{checkedTime(rule.live_check.checked_at)}</p>{rule.live_check.evidence_snippet && <p className="mt-1 max-w-xs text-xs text-calm-700">{rule.live_check.evidence_snippet}</p>}{rule.live_check.read_by && rule.live_check.status !== "error" && <p className="mt-1 text-xs font-bold text-ink">{rule.live_check.read_by === "context.dev" ? "▤ Page read by Context.dev" : "Page read by Exa"}</p>}</td>
            </tr>)}</tbody>
          </table>
          {!data && !error && <p className="p-4 text-sm text-calm-500">Loading latest checks…</p>}
        </div>}
        </div>
      </details>
      <details className="group rounded-2xl bg-white shadow-sm ring-1 ring-calm-100">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-2xl px-5 py-4 hover:bg-calm-50 [&::-webkit-details-marker]:hidden">
          <span><span className="block text-lg font-semibold">How the checks work</span><span className="text-sm text-ink-soft">How Exa, Context.dev and Gemini help</span></span>
          <span aria-hidden="true" className="text-xl text-ink-soft group-open:rotate-180">⌄</span>
        </summary>
        <div className="border-t border-calm-100 p-5 text-sm">
        <ul className="list-inside list-disc space-y-1 text-calm-700">
          <li><strong>Exa</strong> finds the right official pages and the sentences that matter.</li>
          <li><strong>Context.dev</strong> opens the whole page when exact details matter: Migri&apos;s rule page for the daily rule check, and the top page for each perk (the job search certificate, discounts with their price and the proof you need, employer incentives with their conditions). Items read this way are marked “Read from the page by Context.dev”.</li>
          <li><strong>Gemini</strong> checks whether Migri&apos;s page still supports the rule we show.</li>
          <li>Only the public page address is sent to them, never your answers. If a page can&apos;t be read, we use Exa&apos;s summary instead.</li>
        </ul>
        </div>
      </details>
      <details className="group rounded-2xl bg-white shadow-sm ring-1 ring-calm-100">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-2xl px-5 py-4 hover:bg-calm-50 [&::-webkit-details-marker]:hidden">
          <span><span className="block text-lg font-semibold">Trusted websites</span><span className="text-sm text-ink-soft">Official sites we rely on</span></span>
          <span aria-hidden="true" className="text-xl text-ink-soft group-open:rotate-180">⌄</span>
        </summary>
        <div className="border-t border-calm-100 p-5 text-sm">
        <ul className="list-inside list-disc space-y-1 text-calm-700">{(data?.trusted_domains ?? ["migri.fi", "kela.fi", "infofinland.fi", "tyomarkkinatori.fi"]).map((domain) => <li key={domain}>{domain}</li>)}</ul>
        </div>
      </details>
      <details className="group rounded-2xl bg-white shadow-sm ring-1 ring-calm-100" onToggle={load}>
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-2xl px-5 py-4 hover:bg-calm-50 [&::-webkit-details-marker]:hidden">
          <span><span className="block text-lg font-semibold">Source pages</span><span className="text-sm text-ink-soft">Recent public pages behind steps and support</span></span>
          <span aria-hidden="true" className="text-xl text-ink-soft group-open:rotate-180">⌄</span>
        </summary>
        <div className="space-y-3 border-t border-calm-100 p-5">
          {!data && !error && <p className="text-sm text-ink-soft">Loading source pages…</p>}
          {error && <p className="text-sm text-warn">Couldn&apos;t load source pages right now.</p>}
          {data && (!data.sources_used?.length ? <p className="text-sm text-ink-soft">No source pages recorded yet.</p> : Object.entries(groupBy(data.sources_used, (s) => s.step)).map(([step, rows]) => (
            <details key={step} className="group/step rounded-xl ring-1 ring-calm-100">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 font-semibold [&::-webkit-details-marker]:hidden">
                <span>{step} <span className="font-normal text-ink-soft">· {rows.length} {rows.length === 1 ? "page" : "pages"}</span></span>
                <span aria-hidden="true" className="text-xl text-ink-soft group-open/step:rotate-180">⌄</span>
              </summary>
              <ul className="space-y-2 border-t border-calm-100 p-4 text-sm">
                {rows.slice(0, 12).map((s) => (
                  <li key={s.url} className="flex flex-wrap gap-x-2">
                    <a className="underline" href={s.url} target="_blank" rel="noreferrer">{s.title}</a>
                    <span className="text-ink-soft">· {s.domain}{s.date ? ` · page from ${s.date}` : ""}</span>
                  </li>
                ))}
              </ul>
            </details>
          )))}
        </div>
      </details>
      <p className="text-sm text-calm-700">Guidance, not legal advice. For permit decisions, contact Migri or your union.</p>
    </div>
  );
}
