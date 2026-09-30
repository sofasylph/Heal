"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Badge } from "@/components/Badge";
import { api, type PolicySummary, type RawDocument } from "@/lib/api";
import { inr, label } from "@/lib/format";
import { can, useIdentity } from "@/lib/identity";

interface DraftDoc extends RawDocument {
  key: number;
  detected?: string;
  warning?: string | null;
}

let nextKey = 1;

export default function NewClaim() {
  const router = useRouter();
  const { identity } = useIdentity();
  const [policies, setPolicies] = useState<PolicySummary[]>([]);
  const [samples, setSamples] = useState<{ scenario: string; description: string }[]>([]);
  const [policyId, setPolicyId] = useState("SURAKSHA-SILVER");
  const [docs, setDocs] = useState<DraftDoc[]>([]);
  const [expected, setExpected] = useState<{ rec: string; payable: number; description: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.policies().then(setPolicies).catch((e) => setError(String(e)));
    api.samples().then(setSamples).catch(() => {});
  }, []);

  const allowed = can.submit(identity.role);

  async function loadSample(scenario: string) {
    setBusy("Loading sample…");
    setError(null);
    try {
      const s = await api.sample(scenario, policyId);
      setPolicyId(s.policy_id);
      setDocs(s.documents.map((d) => ({ ...d, key: nextKey++ })));
      setExpected({ rec: s.expected_recommendation, payable: s.expected_payable, description: s.description });
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(null);
    }
  }

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setBusy("Reading files…");
    setError(null);
    try {
      const out = await api.extract(Array.from(files));
      setDocs((d) => [
        ...d,
        ...out.map((x) => ({ key: nextKey++, filename: x.filename, text: x.text, detected: x.doc_type, warning: x.warning })),
      ]);
      setExpected(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(null);
    }
  }

  async function submit() {
    setBusy("Adjudicating…");
    setError(null);
    try {
      const claim = await api.createClaim(
        policyId,
        docs.filter((d) => d.text.trim()).map(({ filename, text }) => ({ filename, text })),
      );
      router.push(`/claims/${claim.claim_id}`);
    } catch (e) {
      setError(String(e));
      setBusy(null);
    }
  }

  const update = (key: number, patch: Partial<DraftDoc>) =>
    setDocs((d) => d.map((x) => (x.key === key ? { ...x, ...patch } : x)));

  return (
    <div className="space-y-6">
      <div>
        <Link href="/" className="text-sm text-sky-700 hover:underline">← Back to queue</Link>
        <h1 className="mt-2 text-xl font-semibold">New claim</h1>
        <p className="text-sm text-slate-500">
          Add the claim form, discharge summary and itemised bill as text or PDF (with a text layer), or load a
          synthetic sample. Documents are classified, extracted and adjudicated with the current model settings.
        </p>
      </div>

      {!allowed && (
        <div className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">
          Auditors are read-only. Switch role in the header to submit a claim.
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <div className="space-y-4">
          <label className="block text-sm">
            <span className="text-slate-600">Policy</span>
            <select value={policyId} onChange={(e) => setPolicyId(e.target.value)} className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1.5">
              {policies.map((p) => (
                <option key={p.policy_id} value={p.policy_id}>
                  {p.name} ({p.policy_id}), sum insured {inr(p.sum_insured)}
                </option>
              ))}
            </select>
          </label>

          {docs.length === 0 && (
            <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
              No documents yet. Upload files, add a blank document, or load a sample.
            </div>
          )}

          {docs.map((d) => (
            <div key={d.key} className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <input
                  aria-label="File name"
                  value={d.filename}
                  onChange={(e) => update(d.key, { filename: e.target.value })}
                  className="rounded-md border border-slate-300 px-2 py-1 text-sm"
                />
                {d.detected && <Badge value={d.detected} />}
                <button onClick={() => setDocs((x) => x.filter((y) => y.key !== d.key))} className="ml-auto text-xs text-rose-700 hover:underline">
                  Remove
                </button>
              </div>
              {d.warning && <p className="mb-2 text-xs text-amber-800">{d.warning}</p>}
              <textarea
                aria-label={`${d.filename} text`}
                value={d.text}
                onChange={(e) => update(d.key, { text: e.target.value })}
                rows={8}
                className="w-full rounded-md border border-slate-300 px-2 py-1.5 font-mono text-xs"
              />
            </div>
          ))}

          <div className="flex flex-wrap gap-2 text-sm">
            <label className="cursor-pointer rounded-md bg-white px-3 py-1.5 ring-1 ring-slate-300 hover:bg-slate-50">
              Upload PDF / text
              <input type="file" multiple accept=".pdf,.txt,text/plain,application/pdf" className="hidden" onChange={(e) => upload(e.target.files)} />
            </label>
            <button onClick={() => setDocs((d) => [...d, { key: nextKey++, filename: `document_${d.length + 1}.txt`, text: "" }])} className="rounded-md bg-white px-3 py-1.5 ring-1 ring-slate-300 hover:bg-slate-50">
              Add blank document
            </button>
            <button
              disabled={!allowed || !docs.some((d) => d.text.trim()) || !!busy}
              onClick={submit}
              className="ml-auto rounded-md bg-slate-900 px-4 py-1.5 font-medium text-white hover:bg-slate-700 disabled:opacity-40"
            >
              Submit and adjudicate
            </button>
          </div>
          {busy && <p className="text-sm text-slate-500">{busy}</p>}
          {error && <p className="text-sm text-rose-700">{error}</p>}
        </div>

        <aside className="h-fit space-y-3 rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="font-semibold">Load a sample</h2>
          <p className="text-xs text-slate-500">Synthetic documents for one scenario, with the expected outcome from the reference calculator.</p>
          {expected && (
            <div className="rounded-md bg-sky-50 p-3 text-xs text-sky-900">
              <div className="font-medium">{expected.description}</div>
              <div className="mt-1">
                Expected: {label(expected.rec)} · {inr(expected.payable)}
              </div>
            </div>
          )}
          <ul className="space-y-1">
            {samples.map((s) => (
              <li key={s.scenario}>
                <button onClick={() => loadSample(s.scenario)} className="w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-slate-50">
                  <span className="font-medium">{label(s.scenario)}</span>
                  <span className="block text-xs text-slate-500">{s.description}</span>
                </button>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </div>
  );
}
