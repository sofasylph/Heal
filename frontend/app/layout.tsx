import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "ClaimTrace",
  description: "Evidence-backed decision support for health insurance claims review",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
            <Link href="/" className="flex items-baseline gap-2">
              <span className="text-lg font-semibold tracking-tight">ClaimTrace</span>
              <span className="hidden text-sm text-slate-500 sm:inline">Claims decision workbench</span>
            </Link>
            <span className="rounded bg-amber-50 px-2 py-1 text-xs text-amber-800 ring-1 ring-amber-600/20">
              Synthetic data · decision support only
            </span>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
