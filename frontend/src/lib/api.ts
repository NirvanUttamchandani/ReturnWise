// Typed client for the ReturnWise FastAPI backend. It holds NO business rules:
// every status, label, amount and decision shown in the UI comes from these responses.

export type Tone = "ok" | "warn" | "bad" | "info" | "idle";
export interface Outcome { label: string; tone: Tone }

export interface RequestSummary {
  request_id: string; order_id: string; reason: string; submitted_at: string;
  status: string; is_test: boolean; outcome: Outcome;
  recommended_action: string | null; action_label: string | null;
  eligibility_status: string | null;
  validation_status: string | null; validation_label: string | null;
  refund_amount: number | null; correction_attempted: boolean; error_message: string | null;
}

export interface Check { check: string; passed: boolean; detail: string }

export interface RequestDetail {
  request: {
    request_id: string; order_id: string; reason: string; description: string | null;
    submitted_at: string; status: string; is_test: boolean; error_message: string | null;
  };
  outcome: Outcome;
  recommendation: null | {
    recommendation_id: string; eligibility_status: string; recommended_action: string; action_label: string;
    refund_amount: number | null; policy_explanation: string; validation_status: string; validation_label: string;
    validation_details: string | null; correction_attempted: boolean; correction_details: string | null; created_at: string;
  };
  order: null | { order_id: string; product_name: string; category: string; quantity: number; total_amount: number; status: string; delivery_date: string };
  policy: null | { policy_id: string; category: string; return_window_days: number; returnable: boolean; replacement_only: boolean; notes: string };
  evidence: string[];
  validation_checks: Check[];
  first_validation_errors: string[];
  description_flagged: boolean;
  manual_review_required: boolean;
  is_recommendation_only: boolean;
  duplicate?: boolean;
}

export interface ExecutionStep {
  execution_order: number; agent_name: string; agent_role: string;
  step_type: "agent" | "validation" | "correction" | "revalidation" | "skipped";
  status: "success" | "error" | "skipped" | string; verdict: string | null;
  input_summary: string | null; output_summary: string | null; explanation: string | null;
  executed_at: string; input: Record<string, unknown> | null; output: Record<string, unknown> | null;
}

export interface Metrics {
  total: number; eligible: number; refund_recommended: number; replacement_recommended: number; rejected: number;
  manual_review: number; processing_failed: number; validation_failures: number; correction_attempts: number;
}
export interface MetricsResponse {
  include_tests: boolean; metrics: Metrics;
  status_breakdown: Record<"pending" | "validated" | "manual_review" | "failed", number>;
  validation_failures: RequestSummary[]; manual_review_cases: RequestSummary[];
}
export interface Meta {
  reasons: { value: string; label: string }[]; statuses: { value: string; label: string }[];
  actions: { value: string; label: string }[]; max_description_length: number; reference_date: string;
}
export interface OrderOption { order_id: string; product_name: string; category: string; status: string; total_amount: number }
export interface Page<T> { items: T[]; total: number; limit: number; offset: number }
export interface Scenario { id: string; title: string; order_id: string; reason: string; fault: string | null; kind: string; expect: Record<string, unknown> }
export interface ScenarioCheck { check: string; expected: unknown; actual: unknown; passed: boolean }
export interface ScenarioResult { id: string; request_id: string | null; passed: boolean; checks: ScenarioCheck[]; error: string | null }

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string,
              public fields: Record<string, string> = {}, public requestId?: string) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`https://returnwise-api-pdpk.onrender.com/api${path}`, {
      ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "network_error", "The server could not be reached. Check that the backend is running and try again.");
  }
  let body: unknown = null;
  try { body = await res.json(); } catch { /* non-JSON body */ }
  if (!res.ok) {
    const e = (body as { error?: { code?: string; message?: string; fields?: Record<string, string>; request_id?: string } } | null)?.error;
    throw new ApiError(res.status, e?.code ?? "http_error", e?.message ?? `The server returned an error (${res.status}).`, e?.fields ?? {}, e?.request_id);
  }
  return body as T;
}

const qs = (o: Record<string, string | number | boolean | undefined>) => {
  const p = new URLSearchParams();
  Object.entries(o).forEach(([k, v]) => { if (v !== undefined && v !== "" && v !== false) p.set(k, String(v)); });
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const api = {
  meta: () => call<Meta>("/meta"),
  orders: () => call<{ orders: OrderOption[] }>("/orders"),
  metrics: (includeTests = false) => call<MetricsResponse>(`/metrics${qs({ include_tests: includeTests })}`),
  createRequest: (b: { order_id: string; reason: string; description: string; client_token: string }) =>
    call<RequestDetail>("/requests", { method: "POST", body: JSON.stringify(b) }),
  listRequests: (p: { q?: string; status?: string; action?: string; include_tests?: boolean; limit?: number; offset?: number }) =>
    call<Page<RequestSummary>>(`/requests${qs(p)}`),
  request: (id: string) => call<RequestDetail>(`/requests/${encodeURIComponent(id)}`),
  executions: (id: string) => call<{ request_id: string; steps: ExecutionStep[] }>(`/requests/${encodeURIComponent(id)}/executions`),
  scenarios: () => call<{ scenarios: Scenario[] }>("/scenarios"),
  runScenario: (id: string) => call<ScenarioResult>(`/scenarios/${encodeURIComponent(id)}/run`, { method: "POST" }),
  runAll: () => call<{ results: ScenarioResult[] }>("/scenarios/run-all", { method: "POST" }),
};
