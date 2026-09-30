"use client";

import { useEffect, useState } from "react";
import { ApiError } from "@/components/ApiError";
import { BarList, StatTile } from "@/components/BarList";
import { api, type Analytics } from "@/lib/api";
import { inr, label } from "@/lib/format";

const ROUTE_LABEL: Record<string, string> = {
  auto_candidate: "Auto candidate",
  human_verify: "Human verify",
  escalate: "Escalate",
};

export default function Dashboard() {
  const [a, setA] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.analytics().then(setA).catch((e) => setError(String(e)));
  }, []);

  if (error) return <ApiError message={error} />;
  if (!a) return <p className="text-slate-500">Loading analytics…</p>;

  const pctFmt = (v: number | null) => (v == null ? "—" : `${v}%`);
  const count = (v: number) => v.toLocaleString("en-IN");
  const models = Object.fromEntries(
    Object.entries(a.models_used).flatMap(([stage, m]) => Object.entries(m).map(([name, n]) => [`${label(stage)}: ${name}`, n])),
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <p className="text-sm text-slate-500">
          Portfolio view across {a.decided} adjudicated claims. Final amounts include reviewer decisions.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <StatTile label="Claims adjudicated" value={count(a.decided)} detail={`${a.ai_assisted_claims} AI-assisted`} />
        <StatTile label="Straight-through" value={pctFmt(a.straight_through_pct)} detail="auto-candidate route" />
        <StatTile
          label="Reviewer agreement"
          value={pctFmt(a.reviewer.agreement_pct)}
          detail={`${a.reviewer.finalised} decided · ${a.reviewer.overridden} overridden`}
        />
        <StatTile label="Claimed" value={inr(a.totals.claimed)} />
        <StatTile
          label="Payable (final)"
          value={inr(a.totals.final_payable)}
          detail={`${inr(a.totals.not_paid)} not paid`}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <BarList title="Recommendations" subtitle="Final outcome per claim (reviewer decision where one exists)" data={a.by_recommendation} format={count} labelFormat={label} />
        <BarList title="Review routes" subtitle="Where the system sent each claim" data={a.by_route} format={count} labelFormat={(k) => ROUTE_LABEL[k] ?? label(k)} />
        <BarList title="Deductions by rule" subtitle="INR removed from claimed amounts, by the rule that removed it" data={a.deductions_by_rule} format={inr} empty="No deductions yet." />
        <BarList title="Anomaly flags" subtitle="Investigation signals raised, by type" data={a.anomalies_by_code} format={count} labelFormat={(k) => label(k.toLowerCase())} empty="No anomalies flagged." />
        <BarList
          title="Where reviewers disagree"
          subtitle="Rules involved in claims the reviewer overrode; the first place to look when tuning"
          data={a.reviewer.disagreements_by_rule}
          format={count}
          empty="No overrides yet: reviewers agreed with every decision."
        />
        <BarList title="Decision confidence" subtitle="Claims by overall confidence band" data={a.by_confidence} format={count} />
        <BarList title="Models used" subtitle="Which model produced each stage of each decision" data={models} format={count} />
        <BarList
          title="Payable by policy"
          subtitle="Final payable amount per policy product"
          data={Object.fromEntries(Object.entries(a.by_policy).map(([k, v]) => [k, v.payable]))}
          format={inr}
        />
      </div>
    </div>
  );
}
