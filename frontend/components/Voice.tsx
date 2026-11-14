"use client";

import { useEffect, useRef, useState } from "react";
import { MicIcon, SpeakerIcon, StopIcon } from "./icons";
import { cx } from "./primitives";
import { accessHeaders, useHealth } from "@/lib/access";

/** Whether voice (ElevenLabs) is available for this browser: set up on the server and, if access codes are used,
 *  a valid code entered. Buttons stay hidden until the server says yes. */
export function useVoice(): boolean {
  return !!useHealth()?.voice;
}

export const VOICE_NOTE = "Your recording is sent to ElevenLabs to turn it into text. We don't keep it.";
const MAX_SECONDS = 60;

/** Voice typing: tap the mic to record, tap again to stop; the text is passed to `onText`.
 *  `inside` = a small icon placed inside a text box on the right (the box needs `relative` and right padding). */
export function MicButton({ onText, disabled, className, inside = false }: {
  onText: (text: string) => void; disabled?: boolean; className?: string; inside?: boolean;
}) {
  const on = useVoice();
  const [state, setState] = useState<"idle" | "recording" | "working" | "error">("idle");
  const rec = useRef<MediaRecorder | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); rec.current?.stream.getTracks().forEach((t) => t.stop()); }, []);
  if (!on || typeof window === "undefined" || !("MediaRecorder" in window)) return null;

  async function start() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const type = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find((t) => MediaRecorder.isTypeSupported(t));
      const r = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
      const chunks: Blob[] = [];
      r.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      r.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        if (timer.current) clearTimeout(timer.current);
        setState("working");
        const blob = new Blob(chunks, { type: r.mimeType || "audio/webm" });
        try {
          const res = await fetch("/api/voice/transcribe", { method: "POST", headers: accessHeaders({ "Content-Type": blob.type }), body: blob });
          if (!res.ok) throw new Error(String(res.status));
          const { text } = await res.json();
          if (text) onText(text);
          setState("idle");
        } catch {
          setState("error");
        }
      };
      rec.current = r;
      r.start();
      setState("recording");
      timer.current = setTimeout(() => r.state === "recording" && r.stop(), MAX_SECONDS * 1000);
    } catch {
      setState("error"); // no microphone or permission refused
    }
  }

  const label = state === "recording" ? "Stop recording" : state === "working" ? "Turning your voice into text" : "Speak instead of typing";
  const visibleLabel = state === "recording" ? "Stop recording" : state === "working" ? "Writing it down…" : "Speak instead";
  const status = state === "recording" ? "Listening… tap stop when you're done" : state === "working" ? "Writing it down…"
    : state === "error" ? "Couldn't use the microphone. Please type instead." : "";
  const button = (
    <button type="button" disabled={disabled || state === "working"} aria-label={label} title={`${label}. ${VOICE_NOTE}`}
      onClick={() => (state === "recording" ? rec.current?.stop() : start())}
      className={cx("inline-flex shrink-0 items-center justify-center rounded-full transition-colors disabled:opacity-50",
        inside ? "h-9 w-9 border shadow-sm" : "min-h-11 gap-2 border px-3",
        state === "recording" ? "border-accent bg-accent text-paper motion-safe:animate-pulse"
          : state === "error" ? "border-warn text-warn" : "border-ink/25 bg-card text-ink-soft hover:border-ink hover:text-ink")}>
      {state === "recording" ? <StopIcon /> : state === "working" ? <span aria-hidden className="motion-safe:animate-pulse">…</span> : <MicIcon className={inside ? "h-4 w-4" : "h-5 w-5"} />}
      {!inside && <span className="text-sm font-bold">{visibleLabel}</span>}
    </button>
  );
  if (inside)
    return (
      <span className={cx("absolute right-2 top-2 inline-flex items-center gap-2", className)}>
        {status && <span aria-hidden className="hidden rounded-full bg-card px-2 py-0.5 text-xs text-ink-soft shadow-sm sm:inline">{status}</span>}
        {button}
        <span aria-live="polite" className="sr-only">{status}</span>
      </span>
    );
  return (
    <span className={cx("inline-flex items-center gap-2", className)}>
      {button}
      <span aria-live="polite" className="text-sm text-ink-soft">{status}</span>
    </span>
  );
}

let playing: HTMLAudioElement | null = null;

/** Listen: reads `text` aloud (ElevenLabs). Only one plays at a time. `iconOnly` = a small round speaker button. */
export function ListenButton({ text, label = "Listen", className, iconOnly = false, what }: {
  text: string; label?: string; className?: string; iconOnly?: boolean; what?: string;
}) {
  const on = useVoice();
  const [state, setState] = useState<"idle" | "loading" | "playing" | "error">("idle");
  const audio = useRef<HTMLAudioElement | null>(null);
  useEffect(() => () => { audio.current?.pause(); }, []);
  if (!on) return null;

  async function play() {
    if (state === "playing") { audio.current?.pause(); setState("idle"); return; }
    playing?.pause();
    setState("loading");
    try {
      const res = await fetch("/api/voice/speak", { method: "POST", headers: accessHeaders({ "Content-Type": "application/json" }), body: JSON.stringify({ text: text.slice(0, 1500) }) });
      if (!res.ok) throw new Error(String(res.status));
      const a = new Audio(URL.createObjectURL(await res.blob()));
      a.onended = a.onpause = () => setState("idle");
      audio.current = playing = a;
      await a.play();
      setState("playing");
    } catch {
      setState("error");
    }
  }

  const icon = state === "playing" ? <StopIcon /> : <SpeakerIcon />;
  const words = state === "loading" ? "Loading…" : state === "playing" ? "Stop" : state === "error" ? "Couldn't play" : label;
  if (iconOnly)
    return (
      <button type="button" onClick={play} disabled={state === "loading"} aria-pressed={state === "playing"}
        aria-label={state === "playing" ? "Stop reading aloud" : `Read aloud${what ? `: ${what}` : ""}`} title={state === "error" ? "Couldn't play" : "Read aloud"}
        className={cx("inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-ink/20 bg-card text-ink-soft hover:border-ink hover:text-ink disabled:opacity-60",
          state === "playing" && "border-accent text-accent-ink", state === "loading" && "motion-safe:animate-pulse", className)}>
        {icon}
      </button>
    );
  return (
    <button type="button" onClick={play} disabled={state === "loading"} aria-pressed={state === "playing"}
      className={cx("inline-flex min-h-9 items-center gap-1.5 rounded-full border border-ink/20 bg-card px-3 py-1 text-sm font-bold text-ink hover:border-ink disabled:opacity-60", className)}>
      {icon}{words}
    </button>
  );
}
