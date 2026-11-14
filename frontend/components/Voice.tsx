"use client";

import { useEffect, useRef, useState } from "react";
import { cx } from "./primitives";

/** Whether the backend has voice (ElevenLabs) set up. Asked once per page load; buttons stay hidden until it says yes. */
let voicePromise: Promise<boolean> | null = null;
export function useVoice(): boolean {
  const [on, setOn] = useState(false);
  useEffect(() => {
    voicePromise ??= fetch("/api/health").then((r) => r.json()).then((h) => !!h.voice).catch(() => false);
    voicePromise.then(setOn);
  }, []);
  return on;
}

export const VOICE_NOTE = "Your recording is sent to ElevenLabs to turn it into text. We don't keep it.";
const MAX_SECONDS = 60;

/** 🎤 Voice typing: tap to record, tap again to stop; the text is passed to `onText`. */
export function MicButton({ onText, disabled, className }: { onText: (text: string) => void; disabled?: boolean; className?: string }) {
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
          const res = await fetch("/api/voice/transcribe", { method: "POST", headers: { "Content-Type": blob.type }, body: blob });
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
  return (
    <span className={cx("inline-flex items-center gap-2", className)}>
      <button type="button" disabled={disabled || state === "working"} aria-label={label} title={`${label}. ${VOICE_NOTE}`}
        onClick={() => (state === "recording" ? rec.current?.stop() : start())}
        className={cx("inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full border text-lg transition-colors disabled:opacity-50",
          state === "recording" ? "border-accent bg-accent text-paper motion-safe:animate-pulse" : "border-ink/25 bg-card hover:border-ink")}>
        <span aria-hidden>{state === "working" ? "…" : state === "recording" ? "■" : "🎤"}</span>
      </button>
      <span aria-live="polite" className="text-sm text-ink-soft">
        {state === "recording" ? "Listening… tap ■ when you're done" : state === "working" ? "Writing it down…" : state === "error" ? "Couldn't use the microphone. Please type instead." : ""}
      </span>
    </span>
  );
}

let playing: HTMLAudioElement | null = null;

/** 🔊 Listen: reads `text` aloud (ElevenLabs). Only one plays at a time. */
export function ListenButton({ text, label = "Listen", className }: { text: string; label?: string; className?: string }) {
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
      const res = await fetch("/api/voice/speak", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: text.slice(0, 1500) }) });
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

  return (
    <button type="button" onClick={play} disabled={state === "loading"} aria-pressed={state === "playing"}
      className={cx("inline-flex min-h-9 items-center gap-1.5 rounded-full border border-ink/20 bg-card px-3 py-1 text-sm font-bold text-ink hover:border-ink disabled:opacity-60", className)}>
      <span aria-hidden>{state === "playing" ? "■" : "🔊"}</span>
      {state === "loading" ? "Loading…" : state === "playing" ? "Stop" : state === "error" ? "Couldn't play" : label}
    </button>
  );
}
