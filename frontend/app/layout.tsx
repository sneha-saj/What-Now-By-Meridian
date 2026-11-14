import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "What Now? by Meridian",
  description: "Lost your job in Finland? One calm step at a time.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <nav className="mx-auto flex max-w-2xl gap-4 px-4 pt-6 text-sm text-calm-700">
          <a href="/" className="underline">Home</a>
          <a href="/how-we-know" className="underline">How we know this</a>
        </nav>
        {children}
      </body>
    </html>
  );
}
