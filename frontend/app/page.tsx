"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ApiError } from "@/components/ApiError";
import { Badge, Meter } from "@/components/Badge";
import { api, type ClaimSummary, type Route } from "@/lib/api";
import { inr } from "@/lib/format";

const ROUTE_ORDER: Record<Route, number> = { escalate: 0, human_verify: 1, auto_candidate: 2 };
const FILTERS: { key: Route | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "escalate", label: "Escalated" },
  { key: "human_verify", label: "Verify" },
  { key: "auto_candidate", label: "Auto candidates" },
];

export default function Queue() {
  const [claims, setClaims] = useState<ClaimSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Route | "all">("all");

  useEffect(() => {
    api.claims().then(setClaims).catch((e) => setError(String(e)));
  }, []);

  const rows = useMemo(
    () =>
      (claims ?? [])
        .filter((c) => filter === "all" || c.route === filter)
        .sort((a, b) => ROUTE_ORDER[a.route ?? "auto_candidate"] - ROUTE_ORDER[b.route ?? "auto_candidate"]),
    [claims, filter],
  );

  if (error) return <ApiError message={error} />;
  if (!claims) return <p className="text-slate-500">Loading queue…</p>;

  const count = (r: Route) => claims.filter((c) => c.route === r).length;
  const claimed = claims.reduce((s, c) => s + (c.claimed_amount ?? 0), 0);
  const payable = claims.reduce((s, c) => s + (c.payable_amount ?? 0), 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Review queue</h1>
        <p className="text-sm text-slate-500">Claims ordered by review priority. Every recommendation links to policy clauses and an audit trail.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="Claims" value={String(claims.length)} />
        <Stat label="Escalated" value={String(count("escalate"))} tone="text-rose-700" />
        <Stat label="Needs verification" value={String(count("human_verify"))} tone="text-amber-700" />
        <Stat label="Auto candidates" value={String(count("auto_candidate"))} tone="text-emerald-700" />
        <Stat label="Recommended / claimed" value={`${inr(payable)} / ${inr(claimed)}`} small />
      </div>

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`rounded-md px-3 py-1.5 text-sm ring-1 ring-inset ${
              filter === f.key ? "bg-slate-900 text-white ring-slate-900" : "bg-white text-slate-700 ring-slate-300 hover:bg-slate-50"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Claim</th>
              <th className="px-4 py-3">Patient / diagnosis</th>
              <th className="px-4 py-3 text-right">Claimed</th>
              <th className="px-4 py-3 text-right">Payable</th>
              <th className="px-4 py-3">Recommendation</th>
              <th className="px-4 py-3">Route</th>
              <th className="px-4 py-3">Confidence</th>
              <th className="px-4 py-3">Risk</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((c) => (
              <tr key={c.claim_id} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <Link href={`/claims/${c.claim_id}`} className="font-medium text-sky-700 hover:underline">
                    {c.claim_id}
                  </Link>
                  <div className="text-xs text-slate-500">{c.policy_id}</div>
                </td>
                <td className="px-4 py-3">
                  <div>{c.patient_name ?? "—"}</div>
                  <div className="max-w-xs truncate text-xs text-slate-500">{c.diagnosis ?? "—"}</div>
                </td>
                <td className="px-4 py-3 text-right tabular-nums">{inr(c.claimed_amount)}</td>
                <td className="px-4 py-3 text-right tabular-nums">{inr(c.payable_amount)}</td>
                <td className="px-4 py-3">
                  <Badge value={c.recommendation} />
                  {c.status === "finalised" && <span className="ml-2 text-xs text-slate-500">reviewed</span>}
                </td>
                <td className="px-4 py-3"><Badge value={c.route} /></td>
                <td className="px-4 py-3"><Meter value={c.confidence} /></td>
                <td className="px-4 py-3"><Meter value={c.risk_score} invert /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value, tone = "text-slate-900", small = false }: { label: string; value: string; tone?: string; small?: boolean }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`mt-1 font-semibold tabular-nums ${small ? "text-sm" : "text-2xl"} ${tone}`}>{value}</div>
    </div>
  );
}
