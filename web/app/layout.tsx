import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nepal Market Research Agent",
  description: "Live market signal collection and GTM research for Nepal-focused SaaS products.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="text-ink antialiased">
        <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-6 sm:px-6 lg:px-8">
          <header className="mb-8 flex items-center justify-between rounded-full border border-white/60 bg-white/70 px-5 py-3 shadow-soft backdrop-blur">
            <Link href="/" className="text-sm font-semibold uppercase tracking-[0.24em] text-ocean">
              Nepal Research Agent
            </Link>
            <nav className="flex items-center gap-3 text-sm text-slate-600">
              <Link href="/" className="rounded-full px-3 py-2 transition hover:bg-skywash">
                Dashboard
              </Link>
              <Link
                href="/research/new"
                className="rounded-full bg-ocean px-4 py-2 font-medium text-white transition hover:bg-tide"
              >
                New Research
              </Link>
            </nav>
          </header>
          <div className="flex-1">{children}</div>
        </div>
      </body>
    </html>
  );
}
