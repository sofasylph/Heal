"use client";

import { useEffect, useState } from "react";
import { ApiError } from "@/components/ApiError";
import { api, type CatalogOption, type ModelSettings, type SettingsResponse } from "@/lib/api";
import { can, useIdentity } from "@/lib/identity";

export default function Settings() {
  const { identity } = useIdentity();
  const [data, setData] = useState<SettingsResponse | null>(null);
  const [draft, setDraft] = useState<ModelSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .settings()
      .then((d) => {
        setData(d);
        setDraft(d.settings);
      })
      .catch((e) => setError(String(e)));
  }, []);

  if (error && !data) return <ApiError message={error} />;
  if (!data || !draft) return <p className="text-slate-500">Loading settings…</p>;

  const editable = can.settings(identity.role);
  const dirty = JSON.stringify(draft) !== JSON.stringify(data.settings);
  const set = <K extends keyof ModelSettings>(k: K, v: ModelSettings[K]) => setDraft({ ...draft, [k]: v });

  async function save() {
    if (!draft) return;
    setSaving(true);
    setError(null);
    try {
      const d = await api.saveSettings(draft);
      setData(d);
      setDraft(d.settings);
      setSaved(`Saved as version ${d.version}. New and re-run adjudications use these models.`);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Model settings</h1>
        <p className="text-sm text-slate-500">
          Choose the model for each stage. Every decision records the models that produced it. Version {data.version},
          last changed by {data.updated_by}.
        </p>
      </div>

      {!editable && (
        <div className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">
          Only a senior reviewer can change models. You can view the current configuration.
        </div>
      )}

      <Section title="Document classifier" hint="Labels each uploaded document (claim form, discharge summary, bill…).">
        <Options options={data.catalog.doc_classifier} value={draft.doc_classifier} disabled={!editable} onChange={(v) => set("doc_classifier", v)} name="clf" />
      </Section>

      <Section title="Anomaly detector" hint="Raises investigation flags; a flag routes the claim to a human.">
        <Options options={data.catalog.anomaly_detector} value={draft.anomaly_detector} disabled={!editable} onChange={(v) => set("anomaly_detector", v)} name="anom" />
      </Section>

      <Section
        title="Clause reasoner"
        hint="Reads ambiguous exclusion and waiting-period clauses. Advisory only: it never changes amounts or skips human review, and any failure leaves the claim escalated."
      >
        <Options
          options={data.catalog.reasoner_provider}
          value={draft.reasoner_provider}
          disabled={!editable}
          onChange={(v) => set("reasoner_provider", v as ModelSettings["reasoner_provider"])}
          name="prov"
        />
        {draft.reasoner_provider === "claude" && (
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label className="text-sm">
              <span className="text-slate-600">Claude model</span>
              <select disabled={!editable} value={draft.claude_model} onChange={(e) => set("claude_model", e.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5">
                {data.catalog.claude_model.map((m) => (
                  <option key={m.id} value={m.id}>{m.label}</option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="text-slate-600">Effort (ignored by Haiku)</span>
              <select disabled={!editable} value={draft.claude_effort} onChange={(e) => set("claude_effort", e.target.value as ModelSettings["claude_effort"])} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5">
                {["low", "medium", "high"].map((x) => <option key={x}>{x}</option>)}
              </select>
            </label>
          </div>
        )}
        {draft.reasoner_provider === "ollama" && (
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label className="text-sm">
              <span className="text-slate-600">Model</span>
              <input disabled={!editable} list="ollama-models" value={draft.ollama_model} onChange={(e) => set("ollama_model", e.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5" />
              <datalist id="ollama-models">
                {data.catalog.ollama_installed_models.map((m) => <option key={m} value={m} />)}
              </datalist>
            </label>
            <label className="text-sm">
              <span className="text-slate-600">Ollama URL</span>
              <input disabled={!editable} value={draft.ollama_url} onChange={(e) => set("ollama_url", e.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5" />
            </label>
            <p className="text-xs text-slate-500 sm:col-span-2">
              {data.catalog.ollama_installed_models.length
                ? `Installed: ${data.catalog.ollama_installed_models.join(", ")}`
                : "Ollama is not reachable from the API server. Install it and run `ollama pull qwen3:8b`."}
            </p>
          </div>
        )}
      </Section>

      <div className="flex items-center gap-3">
        <button disabled={!editable || !dirty || saving} onClick={save} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-40">
          {saving ? "Saving…" : "Save settings"}
        </button>
        {dirty && <button onClick={() => setDraft(data.settings)} className="text-sm text-slate-600 hover:underline">Discard changes</button>}
        {saved && !dirty && <span className="text-sm text-emerald-700">{saved}</span>}
        {error && <span className="text-sm text-rose-700">{error}</span>}
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm">
        <div className="font-medium">Active right now</div>
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-6 gap-y-1 text-slate-600">
          {Object.entries(data.active_models).map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-slate-500">{k.replace(/_/g, " ")}</dt>
              <dd className="font-mono text-xs">{v}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-xs text-slate-500">
          How these compare on the synthetic benchmark: <code>docs/eval/model_comparison.md</code> in the repo.
        </p>
      </div>
    </div>
  );
}

function Section({ title, hint, children }: { title: string; hint: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="font-semibold">{title}</h2>
      <p className="mb-3 text-sm text-slate-500">{hint}</p>
      {children}
    </section>
  );
}

function Options({ options, value, onChange, disabled, name }: {
  options: CatalogOption[];
  value: string;
  onChange: (v: string) => void;
  disabled: boolean;
  name: string;
}) {
  return (
    <div className="grid gap-2 sm:grid-cols-3">
      {options.map((o) => {
        const selected = o.id === value;
        return (
          <label
            key={o.id}
            className={`flex cursor-pointer flex-col rounded-md border p-3 text-sm ${
              selected ? "border-slate-900 ring-1 ring-slate-900" : "border-slate-200 hover:border-slate-400"
            } ${disabled ? "cursor-default opacity-80" : ""}`}
          >
            <span className="flex items-center gap-2">
              <input type="radio" name={name} checked={selected} disabled={disabled} onChange={() => onChange(o.id)} />
              <span className="font-medium">{o.label}</span>
            </span>
            {o.description && <span className="mt-1 text-xs text-slate-500">{o.description}</span>}
            {o.available === false && <span className="mt-1 text-xs text-amber-700">Not available on this server; claims will stay escalated.</span>}
          </label>
        );
      })}
    </div>
  );
}
