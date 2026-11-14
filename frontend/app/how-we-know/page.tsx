"use client";

import { useEffect, useState } from "react";
import { api, type RulesResponse } from "@/lib/api";

function checkedTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Time unavailable" : date.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
}

export default function HowWeKnow() {
  const [data, setData] = useState<RulesResponse | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => { api.rules().then(setData).catch(() => setError(true)); }, []);
  return (
    <main id="main" className="mx-auto max-w-5xl space-y-8 px-5 py-12 sm:px-8">
      <header className="space-y-2">
                <h1 className="font-serif text-4xl font-semibold sm:text-5xl">How we know this</h1>
        <p className="text-calm-700">We store each rule with its official source. Once a day, Exa reads the official Migri page and Gemini checks that it still says the same thing. If something looks different, we warn you instead of guessing.</p>
      </header>
      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Finland deadline rules</h2>
        {error && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">We couldn’t load the latest rule checks. Please check Migri directly.</p>}
        <div className="overflow-x-auto rounded-2xl bg-white shadow-sm ring-1 ring-calm-100">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="bg-calm-50 text-calm-700"><tr>
              <th className="p-3 font-semibold">Rule</th><th className="p-3 font-semibold">What it says</th><th className="p-3 font-semibold">Source</th><th className="p-3 font-semibold">In force since</th><th className="p-3 font-semibold">Live check</th>
            </tr></thead>
            <tbody>{data?.rules.map((rule) => <tr key={rule.id} className="border-t border-calm-100 align-top">
              <td className="p-3 font-medium">{rule.months === null ? "Not applicable" : `${rule.months} months`}</td>
              <td className="p-3 text-calm-700">{rule.description}<p className="mt-1 text-xs text-calm-500">Applies to: {rule.applies_to.join(", ")}</p></td>
              <td className="p-3"><a className="text-calm-700 underline" href={rule.source_url} target="_blank" rel="noreferrer">Migri</a></td>
              <td className="p-3">{rule.in_force_since}</td>
              <td className="p-3"><span className={rule.live_check.status === "verified" ? "font-bold text-verified" : rule.live_check.status === "mismatch" ? "font-bold text-warn" : "text-ink-soft"}>{rule.live_check.status === "verified" ? "✓ Matches Migri today" : rule.live_check.status === "mismatch" ? "May have changed" : "Couldn't check right now"}</span><p className="mt-1 text-xs text-calm-500">{checkedTime(rule.live_check.checked_at)}</p>{rule.live_check.evidence_snippet && <p className="mt-1 max-w-xs text-xs text-calm-700">{rule.live_check.evidence_snippet}</p>}</td>
            </tr>)}</tbody>
          </table>
          {!data && !error && <p className="p-4 text-sm text-calm-500">Loading latest checks…</p>}
        </div>
      </section>
      <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-calm-100">
        <h2 className="mb-2 text-xl font-semibold">Trusted websites</h2>
        <ul className="list-inside list-disc space-y-1 text-calm-700">{(data?.trusted_domains ?? ["migri.fi", "kela.fi", "infofinland.fi", "tyomarkkinatori.fi"]).map((domain) => <li key={domain}>{domain}</li>)}</ul>
      </section>
      <p className="text-sm text-calm-700">Guidance, not legal advice. For permit decisions, contact Migri or your union.</p>
    </main>
  );
}
