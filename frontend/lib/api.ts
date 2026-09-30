import { getIdentity } from "@/lib/identity";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Recommendation = "pay" | "partial" | "not_payable" | "needs_info";
export type Route = "auto_candidate" | "human_verify" | "escalate";
export type Outcome = "pass" | "adjust" | "deny" | "needs_info" | "review";

export interface ClaimSummary {
  claim_id: string;
  policy_id: string;
  status: string;
  patient_name: string | null;
  diagnosis: string | null;
  claimed_amount: number | null;
  payable_amount: number | null;
  recommendation: Recommendation | null;
  route: Route | null;
  confidence: number | null;
  risk_score: number | null;
  created_at: string;
}

export interface ClauseRef {
  policy_id: string;
  clause_id: string;
  title: string;
  page: number;
  excerpt: string;
}

export interface ReasonerSuggestion {
  verdict: "applies" | "does_not_apply" | "uncertain";
  rationale: string;
  evidence_quotes: string[];
  missing_information: string[];
  confidence: number;
  model: string;
  prompt_version: string;
  input_sha256: string;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  cached_response: boolean;
}

export interface Finding {
  rule_id: string;
  rule_version: string;
  title: string;
  outcome: Outcome;
  message: string;
  clause: ClauseRef | null;
  amount_impact: number;
  confidence: number;
  deterministic: boolean;
  evidence: Record<string, unknown>;
  suggestion: ReasonerSuggestion | null;
}

export interface AnomalyFlag {
  code: string;
  severity: number;
  message: string;
  evidence: Record<string, unknown>;
}

export interface PayableLine {
  line_id: string;
  description: string;
  category: string;
  claimed: number;
  payable: number;
  notes: string[];
}

export interface Decision {
  recommendation: Recommendation;
  route: Route;
  claimed_amount: number;
  payable_amount: number;
  confidence: number;
  risk_score: number;
  findings: Finding[];
  anomalies: AnomalyFlag[];
  payable_lines: PayableLine[];
  summary: string;
  ai_assisted: boolean;
  models_used: Record<string, string>;
  engine_version: string;
  policy_version: string;
  decided_at: string;
}

export interface ClaimDocument {
  doc_id: string;
  filename: string;
  text: string;
  doc_type: string;
  classification_confidence: number;
  sha256: string;
}

export interface ClaimFacts {
  [key: string]: unknown;
  field_confidence: Record<string, number>;
  field_source: Record<string, string>;
  conflicts: Record<string, string[]>;
}

export interface Override {
  reviewer: string;
  role: string;
  recommendation: Recommendation;
  payable_amount: number;
  reason: string;
  overridden_at: string;
}

export interface Claim {
  claim_id: string;
  policy_id: string;
  status: string;
  documents: ClaimDocument[];
  facts: ClaimFacts | null;
  decision: Decision | null;
  override: Override | null;
  created_at: string;
}

export interface AuditEvent {
  seq: number;
  timestamp: string;
  actor: string;
  action: string;
  payload: Record<string, unknown>;
  prev_hash: string;
  hash: string;
}

export interface AuditTrail {
  claim_id: string;
  chain_valid: boolean;
  events: AuditEvent[];
}

export interface RawDocument {
  filename: string;
  text: string;
  doc_type?: string | null;
}

export interface ExtractedDocument {
  filename: string;
  text: string;
  doc_type: string;
  classification_confidence: number;
  pages: number | null;
  warning: string | null;
}

export interface PolicySummary {
  policy_id: string;
  version: string;
  name: string;
  insurer: string;
  description: string;
  sum_insured: number;
}

export interface SampleClaim {
  scenario: string;
  description: string;
  policy_id: string;
  documents: RawDocument[];
  expected_recommendation: string;
  expected_payable: number;
}

export interface ModelSettings {
  reasoner_provider: "none" | "claude" | "ollama";
  claude_model: string;
  claude_effort: "low" | "medium" | "high";
  ollama_model: string;
  ollama_url: string;
  doc_classifier: string;
  anomaly_detector: string;
}

export interface CatalogOption {
  id: string;
  label: string;
  description?: string;
  available?: boolean;
}

export interface SettingsResponse {
  version: number;
  settings: ModelSettings;
  updated_by: string;
  updated_at: string;
  active_models: Record<string, string>;
  catalog: {
    doc_classifier: CatalogOption[];
    anomaly_detector: CatalogOption[];
    reasoner_provider: CatalogOption[];
    claude_model: CatalogOption[];
    ollama_installed_models: string[];
  };
}

export interface Analytics {
  claims: number;
  decided: number;
  totals: { claimed: number; system_payable: number; final_payable: number; not_paid: number };
  straight_through_pct: number | null;
  ai_assisted_claims: number;
  by_recommendation: Record<string, number>;
  by_route: Record<string, number>;
  by_confidence: Record<string, number>;
  by_policy: Record<string, { claims: number; claimed: number; payable: number }>;
  deductions_by_rule: Record<string, number>;
  anomalies_by_code: Record<string, number>;
  reviewer: {
    finalised: number;
    agreement_pct: number | null;
    overridden: number;
    disagreements_by_rule: Record<string, number>;
  };
  models_used: Record<string, Record<string, number>>;
}

function identityHeaders(): Record<string, string> {
  const { user, role } = getIdentity();
  return { "X-User": user, "X-Role": role };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...identityHeaders(), ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text();
    let detail = body;
    try {
      const parsed = JSON.parse(body);
      detail = typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail);
    } catch {
      /* not JSON */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  claims: () => request<ClaimSummary[]>("/claims"),
  claim: (id: string) => request<Claim>(`/claims/${id}`),
  audit: (id: string) => request<AuditTrail>(`/claims/${id}/audit`),
  adjudicate: (id: string) => request<Claim>(`/claims/${id}/adjudicate`, { method: "POST" }),
  override: (id: string, body: { recommendation: Recommendation; payable_amount: number; reason: string }) =>
    request<Claim>(`/claims/${id}/override`, { method: "POST", body: JSON.stringify(body) }),
  policies: () => request<PolicySummary[]>("/policies"),
  createClaim: (policy_id: string, documents: RawDocument[]) =>
    request<Claim>("/claims", { method: "POST", body: JSON.stringify({ policy_id, documents }) }),
  samples: () => request<{ scenario: string; description: string }[]>("/samples"),
  sample: (scenario: string, policy_id: string) =>
    request<SampleClaim>(`/samples/${scenario}?policy_id=${encodeURIComponent(policy_id)}`),
  extract: async (files: File[]): Promise<ExtractedDocument[]> => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    const res = await fetch(`${API_URL}/documents/extract`, {
      method: "POST",
      body: form,
      headers: identityHeaders(),
    });
    if (!res.ok) throw new Error(`${res.status}: ${(await res.json().catch(() => ({}))).detail ?? res.statusText}`);
    return res.json();
  },
  settings: () => request<SettingsResponse>("/settings"),
  saveSettings: (s: ModelSettings) =>
    request<SettingsResponse>("/settings", { method: "PUT", body: JSON.stringify(s) }),
  analytics: () => request<Analytics>("/analytics"),
};
