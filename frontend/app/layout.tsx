import type { Metadata } from "next";
import { Atkinson_Hyperlegible, Fraunces } from "next/font/google";
import "./globals.css";

const fraunces = Fraunces({ subsets: ["latin"], variable: "--font-fraunces", display: "swap" });
const atkinson = Atkinson_Hyperlegible({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--font-atkinson",
  display: "swap",
});

export const metadata: Metadata = {
  title: "What Now? by Meridian",
  description: "Lost your job in Finland? Calm, sourced next steps: your permit deadline, this week's actions and people who can help.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${fraunces.variable} ${atkinson.variable}`}>
      <body className="min-h-screen antialiased">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-card focus:px-4 focus:py-2">
          Skip to content
        </a>
        <header className="border-b border-rule">
          <nav aria-label="Main" className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-4 sm:px-8">
            <a href="/" className="font-serif text-xl font-semibold tracking-tight">
              What Now?
              <span className="ml-2 font-sans text-sm font-normal text-ink-soft">by Meridian</span>
            </a>
            <div className="flex items-center gap-1 text-[0.95rem]">
              <a href="/start" className="rounded-lg px-3 py-2 hover:bg-paper-deep">Get started</a>
              <a href="/how-we-know" className="rounded-lg px-3 py-2 hover:bg-paper-deep">How we know this</a>
            </div>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
