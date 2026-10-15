import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NewReturn from "../pages/NewReturn";
import { meta, mockApi } from "./helpers";

const orders = { orders: [{ order_id: "ORD-001", product_name: "UltraVision 55 TV", category: "electronics", status: "delivered", total_amount: 45999 }] };
const created = (id = "REQ-NEW1") => ({
  request: { request_id: id, order_id: "ORD-001", reason: "defective", description: null, submitted_at: "2025-02-15T10:00:00+00:00", status: "validated", is_test: false, error_message: null },
  outcome: { label: "Refund Recommended", tone: "ok" },
  recommendation: { recommendation_id: "REC-1", eligibility_status: "eligible", recommended_action: "refund", action_label: "Refund Recommended", refund_amount: 45999, policy_explanation: "x", validation_status: "passed", validation_label: "Recommendation Validated", validation_details: null, correction_attempted: false, correction_details: null, created_at: "" },
  order: null, policy: null, evidence: [], validation_checks: [], first_validation_errors: [], description_flagged: false, manual_review_required: false, is_recommendation_only: true, duplicate: false,
});
const base = { "GET /api/meta": () => ({ body: meta }), "GET /api/orders": () => ({ body: orders }) };
const ui = () => render(<MemoryRouter><NewReturn /></MemoryRouter>);
beforeEach(() => vi.unstubAllGlobals());

describe("New Return form", () => {
  it("validates required fields locally and does not call the API", async () => {
    const calls = mockApi({ ...base });
    ui();
    await userEvent.click(screen.getByRole("button", { name: /Submit return/ }));
    expect(await screen.findByText(/Enter an order ID/)).toBeInTheDocument();
    expect(screen.getByText(/Choose the reason/)).toBeInTheDocument();
    expect(calls.some((c) => c.key === "POST /api/requests")).toBe(false);
  });

  it("shows the request ID and a recommendation-only notice after a saved submit", async () => {
    mockApi({ ...base, "POST /api/requests": () => ({ status: 201, body: created("REQ-NEW1") }) });
    ui();
    await userEvent.type(screen.getByLabelText("Order ID"), "ord-001");
    await userEvent.selectOptions(screen.getByLabelText("Reason for return"), "defective");
    await userEvent.click(screen.getByRole("button", { name: /Submit return/ }));
    expect(await screen.findByTestId("request-id")).toHaveTextContent("REQ-NEW1");
    expect(screen.getByText(/No refund has been paid/)).toBeInTheDocument();
    expect(screen.queryByText(/refunded/i)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /View resolution/ })).toHaveAttribute("href", "/resolution/REQ-NEW1");
  });

  it("sends one request for a double click and keeps the same client token on retry", async () => {
    let n = 0;
    const calls = mockApi({
      ...base,
      "POST /api/requests": async () => { n += 1; await new Promise((r) => setTimeout(r, 30)); return n === 1 ? { status: 500, body: { error: { code: "persistence_failed", message: "The result could not be saved. It was NOT recorded as completed.", request_id: "REQ-FAIL" } } } : { status: 200, body: { ...created("REQ-FAIL"), duplicate: true } }; },
    });
    ui();
    await userEvent.type(screen.getByLabelText("Order ID"), "ORD-001");
    await userEvent.selectOptions(screen.getByLabelText("Reason for return"), "defective");
    const btn = screen.getByRole("button", { name: /Submit return/ });
    await userEvent.dblClick(btn);
    expect(await screen.findByText(/NOT recorded as completed/)).toBeInTheDocument();
    expect(screen.getByText("REQ-FAIL")).toBeInTheDocument();
    expect(calls.filter((c) => c.key === "POST /api/requests")).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: /Submit return/ }));
    await screen.findByTestId("request-id");
    const posts = calls.filter((c) => c.key === "POST /api/requests").map((c) => JSON.parse(String(c.init?.body)).client_token);
    expect(posts).toHaveLength(2);
    expect(posts[0]).toBe(posts[1]);
  });

  it("shows field messages returned by the backend validation", async () => {
    mockApi({ ...base, "POST /api/requests": () => ({ status: 422, body: { error: { code: "validation_error", message: "bad", fields: { order_id: "Order ID may only contain letters, digits and hyphens." } } } }) });
    ui();
    await userEvent.type(screen.getByLabelText("Order ID"), "ORD 1;");
    await userEvent.selectOptions(screen.getByLabelText("Reason for return"), "defective");
    await userEvent.click(screen.getByRole("button", { name: /Submit return/ }));
    expect(await screen.findByText(/may only contain letters/)).toBeInTheDocument();
  });

  it("keeps entries and explains a network failure", async () => {
    mockApi({ ...base, "POST /api/requests": () => { throw new TypeError("offline"); } });
    ui();
    await userEvent.type(screen.getByLabelText("Order ID"), "ORD-001");
    await userEvent.selectOptions(screen.getByLabelText("Reason for return"), "defective");
    await userEvent.click(screen.getByRole("button", { name: /Submit return/ }));
    expect(await screen.findByText(/will not create a duplicate/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Order ID")).toHaveValue("ORD-001"));
  });
});
