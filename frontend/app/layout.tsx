import type { Metadata } from "next";
import "./globals.css";
import { Header } from "@/components/Header";
import { IdentityProvider } from "@/lib/identity";

export const metadata: Metadata = {
  title: "ClaimTrace",
  description: "Evidence-backed decision support for health insurance claims review",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <IdentityProvider>
          <Header />
          <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
          <footer className="mx-auto max-w-7xl px-4 pb-8 text-xs text-slate-400">
            Decision support only. Synthetic policies, claims and patients. Roles are selected, not authenticated (demo).
          </footer>
        </IdentityProvider>
      </body>
    </html>
  );
}
