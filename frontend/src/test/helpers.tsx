import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactElement } from "react";
import { vi } from "vitest";

type Handler = (url: string, init?: RequestInit) => { status?: number; body: unknown } | Promise<{ status?: number; body: unknown }>;

/** Replace fetch with a router keyed by "METHOD /api/path" (query string ignored in the key). */
export function mockApi(routes: Record<string, Handler>) {
  const calls: { key: string; url: string; init?: RequestInit }[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const key = `${init?.method ?? "GET"} ${url.split("?")[0]}`;
    calls.push({ key, url, init });
    const h = routes[key];
    if (!h) throw new Error(`Unmocked request: ${key}`);
    const r = await h(url, init);
    return new Response(JSON.stringify(r.body), { status: r.status ?? 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}

export function renderAt(ui: ReactElement, path = "/", routePath = "*") {
  return render(<MemoryRouter initialEntries={[path]}><Routes><Route path={routePath} element={ui} /></Routes></MemoryRouter>);
}

export const emptyMetrics = {
  include_tests: false,
  metrics: { total: 0, eligible: 0, refund_recommended: 0, replacement_recommended: 0, rejected: 0, manual_review: 0, processing_failed: 0, validation_failures: 0, correction_attempts: 0 },
  status_breakdown: { pending: 0, validated: 0, manual_review: 0, failed: 0 }, validation_failures: [], manual_review_cases: [],
};
export const meta = {
  reasons: [{ value: "defective", label: "Defective or not working" }, { value: "other", label: "Other (needs manual review)" }],
  statuses: [{ value: "validated", label: "Recommendation Validated" }, { value: "failed", label: "Processing Failed" }],
  actions: [{ value: "refund", label: "Refund Recommended" }], max_description_length: 500, reference_date: "2025-02-15",
};
export const summary = (over: Record<string, unknown> = {}) => ({
  request_id: "REQ-AAA", order_id: "ORD-001", reason: "defective", submitted_at: "2025-02-15T10:00:00+00:00", status: "validated", is_test: false,
  outcome: { label: "Refund Recommended", tone: "ok" }, recommended_action: "refund", action_label: "Refund Recommended", eligibility_status: "eligible",
  validation_status: "passed", validation_label: "Recommendation Validated", refund_amount: 45999, correction_attempted: false, error_message: null, ...over,
});
