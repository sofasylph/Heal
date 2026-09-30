"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/components/ApiError";
import { Badge, Meter } from "@/components/Badge";
import { api, type AuditTrail, type Claim, type Finding, type Recommendation } from "@/lib/api";
import { inr, label, pct } from "@/lib/format";

const TABS = ["Decision", "Payable breakdown", "Extracted facts", "Anomalies", "Documents", "Audit trail"] as const;
type Tab = (typeof TABS)[number];

const OUTCOME_ORDER: Record<string, number> = { deny: 0, needs_info: 1, review: 2, adjust: 3, pass: 4 };

export default function ClaimDetail() {
  const { id } = useParams<{ id: string }>();
  const [claim, setClaim] = useState<Claim | null>(null);
  const [audit, setAudit] = useState<AuditTrail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("Decision");

  const load = useCallback(() => {
    Promise.all([api.claim(id), api.audit(id)])
      .then(([c, a]) => {
        setClaim(c);
        setAudit(a);
      })
      .catch((e) => setError(String(e)));
  }, [id]);

  useEffect(load, [load]);

  if (error) return <ApiError message={error} />;
  if (!claim) return <p className="text-slate-500">Loading claim…</p>;
  const d = claim.decision;
  const f = claim.facts;

  return (
    <div className="space-y-6">
      <Link href="/" className="text-sm text-sky-700 hover:underline">← Back to queue</Link>

      <div className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold">{claim.claim_id}</h1>
            <Badge value={d?.recommendation} />
            <Badge value={d?.route} />
            {claim.override && <span className="text-xs text-slate-500">reviewed by {claim.override.reviewer}</span>}
          </div>
          <p className="text-sm text-slate-600">
            {String(f?.patient_name ?? "Unknown patient")} · {String(f?.diagnosis ?? "diagnosis not extracted")} · {claim.policy_id}
          </p>
          {d && <p className="max-w-3xl pt-2 text-sm text-slate-800">{d.summary}</p>}
        </div>
        {d && (
          <dl className="grid shrink-0 grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <dt className="text-slate-500">Claimed</dt>
            <dd className="text-right font-medium tabular-nums">{inr(d.claimed_amount)}</dd>
            <dt className="text-slate-500">Recommended</dt>
            <dd className="text-right font-semibold tabular-nums">{inr(d.payable_amount)}</dd>
            {claim.override && (
              <>
                <dt className="text-slate-500">Final (reviewer)</dt>
                <dd className="text-right font-semibold tabular-nums text-sky-700">{inr(claim.override.payable_amount)}</dd>
              </>
            )}
            <dt className="text-slate-500">Confidence</dt>
            <dd className="flex justify-end"><Meter value={d.confidence} /></dd>
            <dt className="text-slate-500">Risk</dt>
            <dd className="flex justify-end"><Meter value={d.risk_score} invert /></dd>
          </dl>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="min-w-0">
          <div className="mb-4 flex gap-1 overflow-x-auto border-b border-slate-200">
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`whitespace-nowrap border-b-2 px-3 py-2 text-sm ${
                  tab === t ? "border-slate-900 font-medium text-slate-900" : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                {t}
                {t === "Anomalies" && d?.anomalies.length ? ` (${d.anomalies.length})` : ""}
              </button>
            ))}
          </div>
          {tab === "Decision" && d && <Findings findings={d.findings} />}
          {tab === "Payable breakdown" && d && <Breakdown claim={claim} />}
          {tab === "Extracted facts" && <Facts claim={claim} />}
          {tab === "Anomalies" && d && <Anomalies claim={claim} />}
          {tab === "Documents" && <Documents claim={claim} />}
          {tab === "Audit trail" && audit && <Audit trail={audit} />}
        </div>
        <ReviewerPanel claim={claim} onSaved={load} />
      </div>
    </div>
  );
}

function Findings({ findings }: { findings: Finding[] }) {
  const sorted = [...findings].sort((a, b) => OUTCOME_ORDER[a.outcome] - OUTCOME_ORDER[b.outcome]);
  return (
    <ul className="space-y-3">
      {sorted.map((f, i) => (
        <li key={i} className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Badge value={f.outcome} />
              <span className="font-medium">{f.title}</span>
              <span className="text-xs text-slate-400">{f.rule_id} v{f.rule_version}</span>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-500">
              {f.amount_impact !== 0 && <span className="font-medium tabular-nums text-rose-700">{inr(f.amount_impact)}</span>}
              <span>{f.deterministic ? "deterministic" : "judgement"}</span>
              <Meter value={f.confidence} />
            </div>
          </div>
          <p className="mt-2 text-sm text-slate-700">{f.message}</p>
          {f.clause && (
            <blockquote className="mt-3 border-l-2 border-sky-300 bg-sky-50/50 px-3 py-2 text-xs text-slate-600">
              <div className="mb-1 font-medium text-sky-800">
                {f.clause.policy_id} · Clause {f.clause.clause_id} “{f.clause.title}” · page {f.clause.page}
              </div>
              {f.clause.excerpt}
            </blockquote>
          )}
        </li>
      ))}
    </ul>
  );
}

function Breakdown({ claim }: { claim: Claim }) {
  const d = claim.decision!;
  const lineTotal = d.payable_lines.reduce((s, l) => s + l.payable, 0);
  const claimLevel = d.findings.filter((f) => ["SUBL-001", "SI-001", "DED-001", "COPAY-001"].includes(f.rule_id) && f.amount_impact);
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-2">Line item</th>
            <th className="px-4 py-2">Category</th>
            <th className="px-4 py-2 text-right">Claimed</th>
            <th className="px-4 py-2 text-right">Payable</th>
            <th className="px-4 py-2">Notes</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {d.payable_lines.map((l) => (
            <tr key={l.line_id}>
              <td className="px-4 py-2">{l.description}</td>
              <td className="px-4 py-2 text-slate-500">{label(l.category)}</td>
              <td className="px-4 py-2 text-right tabular-nums">{inr(l.claimed)}</td>
              <td className={`px-4 py-2 text-right tabular-nums ${l.payable < l.claimed ? "text-rose-700" : ""}`}>{inr(l.payable)}</td>
              <td className="px-4 py-2 text-xs text-slate-500">{l.notes.join("; ")}</td>
            </tr>
          ))}
          <tr className="bg-slate-50 font-medium">
            <td className="px-4 py-2" colSpan={3}>Line-level payable</td>
            <td className="px-4 py-2 text-right tabular-nums">{inr(lineTotal)}</td>
            <td />
          </tr>
          {claimLevel.map((f) => (
            <tr key={f.rule_id}>
              <td className="px-4 py-2" colSpan={3}>{f.title} (clause {f.clause?.clause_id})</td>
              <td className="px-4 py-2 text-right tabular-nums text-rose-700">{inr(f.amount_impact)}</td>
              <td />
            </tr>
          ))}
          <tr className="bg-slate-50 font-semibold">
            <td className="px-4 py-2" colSpan={3}>Recommended payable</td>
            <td className="px-4 py-2 text-right tabular-nums">{inr(d.payable_amount)}</td>
            <td />
          </tr>
        </tbody>
      </table>
    </div>
  );
}

const FACT_FIELDS = [
  "patient_name", "patient_age", "policy_number", "policy_start_date", "hospital", "diagnosis", "procedure",
  "admission_date", "discharge_date", "room_type", "room_rent_per_day", "pre_existing_conditions", "claimed_amount",
];

function Facts({ claim }: { claim: Claim }) {
  const f = claim.facts;
  if (!f) return <p className="text-sm text-slate-500">No facts extracted.</p>;
  const docName = (docId?: string) => claim.documents.find((d) => d.doc_id === docId)?.filename ?? "—";
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-2">Field</th>
            <th className="px-4 py-2">Value</th>
            <th className="px-4 py-2">Confidence</th>
            <th className="px-4 py-2">Source</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {FACT_FIELDS.map((k) => {
            const v = f[k];
            const conflict = f.conflicts[k];
            return (
              <tr key={k} className={conflict ? "bg-violet-50/60" : ""}>
                <td className="px-4 py-2 text-slate-500">{label(k)}</td>
                <td className="px-4 py-2">
                  {Array.isArray(v) ? (v.length ? v.join(", ") : "None") : v == null ? <span className="text-rose-600">not found</span> : String(v)}
                  {conflict && <div className="text-xs text-violet-700">Conflict across documents: {conflict.join(" vs ")}</div>}
                </td>
                <td className="px-4 py-2">{f.field_confidence[k] != null ? <Meter value={f.field_confidence[k]} /> : "—"}</td>
                <td className="px-4 py-2 text-xs text-slate-500">{docName(f.field_source[k])}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Anomalies({ claim }: { claim: Claim }) {
  const a = claim.decision!.anomalies;
  if (!a.length) return <p className="text-sm text-slate-500">No anomaly signals. Risk score {pct(claim.decision!.risk_score)}.</p>;
  return (
    <ul className="space-y-3">
      {a.map((x) => (
        <li key={x.code} className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex items-center justify-between">
            <span className="font-medium">{label(x.code.toLowerCase())}</span>
            <Meter value={x.severity} invert />
          </div>
          <p className="mt-1 text-sm text-slate-700">{x.message}</p>
          <pre className="mt-2 overflow-x-auto rounded bg-slate-50 p-2 text-xs text-slate-600">{JSON.stringify(x.evidence, null, 2)}</pre>
        </li>
      ))}
      <li className="text-xs text-slate-500">Anomaly signals prioritise investigation; they are not a fraud determination.</li>
    </ul>
  );
}

function Documents({ claim }: { claim: Claim }) {
  return (
    <div className="space-y-4">
      {claim.documents.map((doc) => (
        <details key={doc.doc_id} className="rounded-lg border border-slate-200 bg-white" open={claim.documents.length === 1}>
          <summary className="flex cursor-pointer flex-wrap items-center gap-2 px-4 py-3 text-sm">
            <span className="font-medium">{doc.filename}</span>
            <Badge value={doc.doc_type} />
            <span className="text-xs text-slate-500">classified at {pct(doc.classification_confidence)} · sha256 {doc.sha256.slice(0, 12)}…</span>
          </summary>
          <pre className="overflow-x-auto whitespace-pre-wrap border-t border-slate-100 px-4 py-3 text-xs text-slate-700">{doc.text}</pre>
        </details>
      ))}
    </div>
  );
}

function Audit({ trail }: { trail: AuditTrail }) {
  return (
    <div className="space-y-3">
      <div className={`rounded-md px-3 py-2 text-sm ${trail.chain_valid ? "bg-emerald-50 text-emerald-800" : "bg-rose-50 text-rose-800"}`}>
        {trail.chain_valid
          ? `Hash chain verified: ${trail.events.length} events, untampered.`
          : "Hash chain verification FAILED: audit history has been altered."}
      </div>
      <ol className="space-y-2">
        {trail.events.map((e) => (
          <li key={e.seq} className="rounded-lg border border-slate-200 bg-white">
            <details>
              <summary className="flex cursor-pointer flex-wrap items-center gap-3 px-4 py-2 text-sm">
                <span className="tabular-nums text-slate-400">#{e.seq}</span>
                <span className="font-medium">{label(e.action)}</span>
                <span className="text-slate-500">{e.actor}</span>
                <span className="text-xs text-slate-400">{new Date(e.timestamp).toLocaleString()}</span>
                <code className="ml-auto text-xs text-slate-400">{e.hash.slice(0, 10)}…</code>
              </summary>
              <pre className="max-h-96 overflow-auto border-t border-slate-100 px-4 py-3 text-xs text-slate-700">{JSON.stringify(e.payload, null, 2)}</pre>
            </details>
          </li>
        ))}
      </ol>
    </div>
  );
}

const RECS: Recommendation[] = ["pay", "partial", "not_payable", "needs_info"];

function ReviewerPanel({ claim, onSaved }: { claim: Claim; onSaved: () => void }) {
  const d = claim.decision;
  const [reviewer, setReviewer] = useState("");
  const [rec, setRec] = useState<Recommendation>(d?.recommendation ?? "pay");
  const [amount, setAmount] = useState<number>(d?.payable_amount ?? 0);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (!d) return null;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErr(null);
    try {
      await api.override(claim.claim_id, { reviewer, recommendation: rec, payable_amount: amount, reason });
      setReason("");
      onSaved();
    } catch (e) {
      setErr(String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <aside className="h-fit space-y-4 rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="font-semibold">Reviewer decision</h2>
      {claim.override && (
        <div className="rounded-md bg-sky-50 p-3 text-sm text-sky-900">
          <div className="font-medium">
            Final: {label(claim.override.recommendation)} · {inr(claim.override.payable_amount)}
          </div>
          <div className="mt-1 text-xs">“{claim.override.reason}” by {claim.override.reviewer}</div>
        </div>
      )}
      <form onSubmit={submit} className="space-y-3 text-sm">
        <label className="block">
          <span className="text-slate-600">Reviewer</span>
          <input required value={reviewer} onChange={(e) => setReviewer(e.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5" placeholder="your name" />
        </label>
        <label className="block">
          <span className="text-slate-600">Decision</span>
          <select value={rec} onChange={(e) => setRec(e.target.value as Recommendation)} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5">
            {RECS.map((r) => <option key={r} value={r}>{label(r)}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="text-slate-600">Payable amount (INR)</span>
          <input type="number" min={0} step="0.01" value={amount} onChange={(e) => setAmount(Number(e.target.value))} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 tabular-nums" />
        </label>
        <label className="block">
          <span className="text-slate-600">Reason (recorded in audit trail)</span>
          <textarea required minLength={3} value={reason} onChange={(e) => setReason(e.target.value)} rows={3} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5" />
        </label>
        {err && <p className="text-xs text-rose-700">{err}</p>}
        <button disabled={saving} className="w-full rounded-md bg-slate-900 px-3 py-2 font-medium text-white hover:bg-slate-700 disabled:opacity-50">
          {saving ? "Saving…" : "Record decision"}
        </button>
        <p className="text-xs text-slate-500">
          The system recommends; a human decides. Agreeing or overriding both land in the hash-chained audit log.
        </p>
      </form>
    </aside>
  );
}
