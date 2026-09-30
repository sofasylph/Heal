const TONES: Record<string, string> = {
  pay: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  partial: "bg-sky-50 text-sky-700 ring-sky-600/20",
  not_payable: "bg-rose-50 text-rose-700 ring-rose-600/20",
  needs_info: "bg-amber-50 text-amber-800 ring-amber-600/20",
  auto_candidate: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  human_verify: "bg-amber-50 text-amber-800 ring-amber-600/20",
  escalate: "bg-rose-50 text-rose-700 ring-rose-600/20",
  pass: "bg-slate-50 text-slate-600 ring-slate-500/20",
  adjust: "bg-sky-50 text-sky-700 ring-sky-600/20",
  deny: "bg-rose-50 text-rose-700 ring-rose-600/20",
  review: "bg-violet-50 text-violet-700 ring-violet-600/20",
};

const TEXT: Record<string, string> = {
  auto_candidate: "Auto candidate",
  human_verify: "Verify",
  escalate: "Escalate",
  not_payable: "Not payable",
  needs_info: "Needs info",
};

export function Badge({ value }: { value: string | null | undefined }) {
  if (!value) return <span className="text-slate-400">—</span>;
  const tone = TONES[value] ?? "bg-slate-50 text-slate-600 ring-slate-500/20";
  const text = TEXT[value] ?? value.charAt(0).toUpperCase() + value.slice(1);
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${tone}`}>
      {text}
    </span>
  );
}

export function Meter({ value, invert = false }: { value: number | null | undefined; invert?: boolean }) {
  if (value == null) return <span className="text-slate-400">—</span>;
  const good = invert ? value < 0.3 : value >= 0.9;
  const mid = invert ? value < 0.6 : value >= 0.7;
  const color = good ? "bg-emerald-500" : mid ? "bg-amber-500" : "bg-rose-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 rounded-full bg-slate-200">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${Math.max(value * 100, 4)}%` }} />
      </div>
      <span className="tabular-nums text-xs text-slate-600">{Math.round(value * 100)}%</span>
    </div>
  );
}
