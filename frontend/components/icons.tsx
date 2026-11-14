/** Small line icons. Decorative: always paired with text or an sr-only label. */
type P = { className?: string };
const base = "inline-block shrink-0";

export function PersonIcon({ className = "h-4 w-4" }: P) {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="8" cy="5" r="2.75" />
      <path d="M2.75 14c.6-2.9 2.7-4.5 5.25-4.5s4.65 1.6 5.25 4.5" strokeLinecap="round" />
    </svg>
  );
}

export function GlobeIcon({ className = "h-4 w-4" }: P) {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="8" cy="8" r="6.25" />
      <path d="M1.75 8h12.5M8 1.75c1.8 1.9 2.6 4 2.6 6.25S9.8 12.35 8 14.25C6.2 12.35 5.4 10.25 5.4 8S6.2 3.65 8 1.75Z" />
    </svg>
  );
}

export function SearchIcon({ className = "h-4 w-4" }: P) {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="7" cy="7" r="4.5" strokeDasharray="2.2 1.6" />
      <path d="m10.5 10.5 3.25 3.25" strokeLinecap="round" />
    </svg>
  );
}

export function CheckIcon({ className = "h-4 w-4" }: P) {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m3.5 8.5 3 3 6-7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function PencilIcon({ className = "h-3.5 w-3.5" }: P) {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M10.5 2.5 13.5 5.5 5.5 13.5H2.5v-3l8-8Z" strokeLinejoin="round" />
    </svg>
  );
}

export function MicIcon({ className = "h-4 w-4" }: P) {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <rect x="5.75" y="1.75" width="4.5" height="8" rx="2.25" />
      <path d="M3.5 7.5a4.5 4.5 0 0 0 9 0M8 12v2.25" />
    </svg>
  );
}

export function SpeakerIcon({ className = "h-4 w-4" }: P) {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2.25 6v4h2.5l3.5 3V3l-3.5 3h-2.5Z" />
      <path d="M10.75 5.75a3.2 3.2 0 0 1 0 4.5M12.6 4a5.7 5.7 0 0 1 0 8" />
    </svg>
  );
}

export function StopIcon({ className = "h-3.5 w-3.5" }: P) {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className={`${base} ${className}`} fill="currentColor">
      <rect x="3.5" y="3.5" width="9" height="9" rx="1.5" />
    </svg>
  );
}
