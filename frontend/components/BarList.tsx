"use client";

import { useState } from "react";

/** Single-series horizontal bars: one hue, value at the tip in text ink, a hover/focus
 * tooltip per bar, and a table view so no value depends on hovering or on colour. */
export function BarList({
  title,
  subtitle,
  data,
  format = (v) => v.toLocaleString("en-IN"),
  labelFormat = (k) => k,
  empty = "Nothing yet.",
}: {
  title: string;
  subtitle?: string;
  data: Record<string, number>;
  format?: (v: number) => string;
  labelFormat?: (k: string) => string;
  empty?: string;
}) {
  const [table, setTable] = useState(false);
  const [hover, setHover] = useState<string | null>(null);
  const rows = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...rows.map(([, v]) => v), 0);
  const total = rows.reduce((s, [, v]) => s + v, 0);

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
        </div>
        {rows.length > 0 && (
          <button onClick={() => setTable((t) => !t)} className="text-xs text-slate-500 hover:text-slate-800 hover:underline">
            {table ? "Chart" : "Table"}
          </button>
        )}
      </div>

      {rows.length === 0 && <p className="text-sm text-slate-400">{empty}</p>}

      {rows.length > 0 && table && (
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-500">
            <tr><th className="py-1 font-normal">Category</th><th className="py-1 text-right font-normal">Value</th><th className="py-1 text-right font-normal">Share</th></tr>
          </thead>
          <tbody>
            {rows.map(([k, v]) => (
              <tr key={k} className="border-t border-slate-100">
                <td className="py-1 text-slate-700">{labelFormat(k)}</td>
                <td className="py-1 text-right tabular-nums">{format(v)}</td>
                <td className="py-1 text-right tabular-nums text-slate-500">{total ? `${Math.round((100 * v) / total)}%` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {rows.length > 0 && !table && (
        <ul className="space-y-1.5" role="list">
          {rows.map(([k, v]) => {
            const pct = max ? (100 * v) / max : 0;
            const active = hover === k;
            return (
              <li
                key={k}
                tabIndex={0}
                onPointerEnter={() => setHover(k)}
                onPointerLeave={() => setHover(null)}
                onFocus={() => setHover(k)}
                onBlur={() => setHover(null)}
                aria-label={`${labelFormat(k)}: ${format(v)}`}
                className={`relative grid grid-cols-[minmax(0,40%)_1fr] items-center gap-3 rounded px-1 py-1 outline-none ${active ? "bg-slate-50" : ""} focus-visible:ring-2 focus-visible:ring-slate-400`}
              >
                <span className="truncate text-xs text-slate-600" title={labelFormat(k)}>{labelFormat(k)}</span>
                <span className="flex items-center gap-2">
                  <span
                    className="h-4 rounded-r transition-opacity"
                    style={{ width: `${Math.max(pct, 1.5)}%`, background: "var(--series-1)", opacity: active ? 0.85 : 1 }}
                  />
                  <span className="whitespace-nowrap text-xs tabular-nums text-slate-800">{format(v)}</span>
                </span>
                {active && (
                  <span role="tooltip" className="pointer-events-none absolute -top-9 right-2 z-10 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs shadow-sm">
                    <strong className="text-slate-900">{format(v)}</strong>
                    <span className="ml-1 text-slate-500">{labelFormat(k)}{total ? ` · ${Math.round((100 * v) / total)}% of total` : ""}</span>
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export function StatTile({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{value}</div>
      {detail && <div className="mt-1 text-xs text-slate-500">{detail}</div>}
    </div>
  );
}
