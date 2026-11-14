"use client";

import { useState } from "react";
import type { Contact, Draft, ReferralResponse } from "@/lib/api";
import { Button, Card, SourceChip, cx, formatDate, hostOf } from "./primitives";

const SHOW = 5;

function useShowMore<T>(items: T[]) {
  const [all, setAll] = useState(false);
  return { shown: all ? items : items.slice(0, SHOW), more: items.length - SHOW, all, toggle: () => setAll(!all) };
}

function ShowMore({ more, all, toggle, noun }: { more: number; all: boolean; toggle: () => void; noun: string }) {
  if (more <= 0) return null;
  return <Button variant="quiet" onClick={toggle}>{all ? "Show fewer" : `Show ${more} more ${noun}`}</Button>;
}

function ContactCard({
  c, draft, text, onText,
}: { c: Contact; draft?: Draft; text: string; onText: (t: string) => void }) {
  const [copied, setCopied] = useState(false);
  const id = `draft-${c.profile_url}`;
  return (
    <li className="rounded-2xl border border-rule bg-card p-5 shadow-[0_2px_12px_rgba(28,42,69,0.05)]">
      <p className="font-serif text-xl font-semibold">{c.name}</p>
      <p className="text-ink-soft">{c.role}{c.role && " · "}{c.company}</p>
      <p className="mt-2"><span className="text-ink-soft">Why this person: </span>{c.why_this_person}</p>
      <div className="mt-2"><SourceChip source={{ title: "Public profile", url: c.profile_url }} /></div>
      {draft && (
        <div className="mt-4">
          <label htmlFor={id} className="font-bold">Your draft message</label>
          <p className="text-sm text-ink-soft">Edit it so it sounds like you. Nothing is sent: copy it and send it yourself.</p>
          <textarea id={id} value={text} onChange={(e) => { onText(e.target.value); setCopied(false); }} rows={5}
            className="mt-2 w-full rounded-xl border border-ink/25 bg-paper p-3" />
          <div className="mt-2 flex items-center gap-3">
            <Button variant="chip" onClick={async () => {
              try { await navigator.clipboard.writeText(text); setCopied(true); } catch { setCopied(false); }
            }}>
              {copied ? "Copied ✓" : "Copy message"}
            </Button>
            <span aria-live="polite" className="sr-only">{copied ? "Copied to clipboard" : ""}</span>
            <span className="text-sm text-ink-soft">{text.trim().split(/\s+/).length} words</span>
          </div>
        </div>
      )}
    </li>
  );
}

/** Step 4. Max 5 of each, "Show more" for the rest. Drafts are editable and never sent. */
export function FindYourWayIn({
  r, drafts, onDraft,
}: { r: ReferralResponse; drafts: Record<string, string>; onDraft: (url: string, text: string) => void }) {
  const companies = useShowMore(r.companies);
  const contacts = useShowMore(r.contacts);
  const communities = useShowMore(r.communities);
  const nothing = !r.companies.length && !r.contacts.length && !r.communities.length;

  return (
    <section aria-labelledby="way-title" className="space-y-8">
      <div>
        <h2 id="way-title" className="font-serif text-4xl font-semibold">Find your way in</h2>
        <p className="mt-2 text-lg text-ink-soft">Most jobs in Finland are found through people. Here are some places to start.</p>
      </div>
      {nothing && <p>We couldn&apos;t find anything right now. Try again later, or ask International House or your union.</p>}

      {r.companies.length > 0 && (
        <Card title="Companies">
          <ul className="space-y-4">
            {companies.shown.map((c, i) => (
              <li key={i} className="border-b border-rule pb-4 last:border-0 last:pb-0">
                <div className="flex flex-wrap items-center gap-2">
                  <a href={c.url} target="_blank" rel="noreferrer" className="font-serif text-xl font-semibold underline decoration-rule underline-offset-4 hover:decoration-ink">
                    {c.name}<span className="sr-only"> (opens in a new tab)</span>
                  </a>
                  <span className={cx("rounded-full px-2.5 py-0.5 text-sm font-bold",
                    c.hiring_now ? "bg-verified-soft text-verified" : "bg-paper-deep text-ink-soft")}>
                    {c.hiring_now ? "Hiring now" : "May be hiring"}
                  </span>
                </div>
                <p className="mt-1">{c.why_relevant}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <SourceChip source={{ title: c.name, url: c.url }} />
                  {c.hiring_evidence && c.hiring_evidence !== c.url && (
                    <SourceChip source={{ title: "Job post", url: c.hiring_evidence }} />
                  )}
                </div>
              </li>
            ))}
          </ul>
          <div className="mt-3"><ShowMore {...companies} noun="companies" /></div>
        </Card>
      )}

      {r.contacts.length > 0 && (
        <div className="space-y-4">
          <h3 className="font-serif text-2xl font-semibold">People you could message</h3>
          <ul className="space-y-4">
            {contacts.shown.map((c) => {
              const draft = r.drafts.find((d) => d.profile_url === c.profile_url);
              return (
                <ContactCard key={c.profile_url} c={c} draft={draft}
                  text={drafts[c.profile_url] ?? draft?.message ?? ""} onText={(t) => onDraft(c.profile_url, t)} />
              );
            })}
          </ul>
          <ShowMore {...contacts} noun="people" />
        </div>
      )}

      {r.communities.length > 0 && (
        <Card title="Communities and events">
          <ul className="space-y-3">
            {communities.shown.map((g, i) => (
              <li key={i} className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="rounded-full bg-accent-soft px-2.5 py-0.5 text-sm font-bold text-accent-ink">
                  {g.type === "event" ? "Event" : g.type === "union" ? "Union" : "Group"}
                </span>
                <a href={g.url} target="_blank" rel="noreferrer" className="font-bold underline decoration-rule underline-offset-4 hover:decoration-ink">
                  {g.name}<span className="sr-only"> (opens in a new tab)</span>
                </a>
                <span className="text-sm text-ink-soft">{g.date_if_event ? formatDate(g.date_if_event) : hostOf(g.url)}</span>
              </li>
            ))}
          </ul>
          <div className="mt-3"><ShowMore {...communities} noun="communities" /></div>
        </Card>
      )}
    </section>
  );
}
