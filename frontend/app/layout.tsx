import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "What Now? by Meridian",
  description: "Lost your job in Finland? One calm step at a time.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
