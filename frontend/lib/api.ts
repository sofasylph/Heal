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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  claims: () => request<ClaimSummary[]>("/claims"),
  claim: (id: string) => request<Claim>(`/claims/${id}`),
  audit: (id: string) => request<AuditTrail>(`/claims/${id}/audit`),
  adjudicate: (id: string) => request<Claim>(`/claims/${id}/adjudicate`, { method: "POST" }),
  override: (
    id: string,
    body: { reviewer: string; recommendation: Recommendation; payable_amount: number; reason: string },
  ) => request<Claim>(`/claims/${id}/override`, { method: "POST", body: JSON.stringify(body) }),
};
