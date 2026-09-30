"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ROLES, type Role, useIdentity } from "@/lib/identity";

const NAV = [
  { href: "/", label: "Queue" },
  { href: "/claims/new", label: "New claim" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/settings", label: "Settings" },
];

export function Header() {
  const path = usePathname();
  const { identity, setIdentity } = useIdentity();
  const [name, setName] = useState(identity.user);
  const role = ROLES.find((r) => r.id === identity.role);

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3">
        <Link href="/" className="flex items-baseline gap-2">
          <span className="text-lg font-semibold tracking-tight">ClaimTrace</span>
          <span className="hidden text-xs text-amber-700 lg:inline">synthetic data</span>
        </Link>
        <nav className="flex flex-wrap gap-1 text-sm">
          {NAV.map((n) => {
            const active = n.href === "/" ? path === "/" : path.startsWith(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                className={`rounded-md px-3 py-1.5 ${active ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-2 text-sm" title={role?.description}>
          <span className="hidden text-xs text-slate-500 sm:inline">Acting as</span>
          <input
            aria-label="Your name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={() => name.trim() && setIdentity({ ...identity, user: name.trim() })}
            className="w-32 rounded-md border border-slate-300 px-2 py-1"
          />
          <select
            aria-label="Role"
            value={identity.role}
            onChange={(e) => setIdentity({ ...identity, role: e.target.value as Role })}
            className="rounded-md border border-slate-300 px-2 py-1"
          >
            {ROLES.map((r) => (
              <option key={r.id} value={r.id}>
                {r.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </header>
  );
}
