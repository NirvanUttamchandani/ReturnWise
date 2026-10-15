import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Overview from "../pages/Overview";
import { emptyMetrics, meta, mockApi, summary } from "./helpers";

const ui = () => render(<MemoryRouter><Overview /></MemoryRouter>);
beforeEach(() => vi.unstubAllGlobals());

describe("Overview", () => {
  it("shows a loading state first, then real metric values", async () => {
    mockApi({
      "GET /api/metrics": () => ({ body: { ...emptyMetrics, metrics: { ...emptyMetrics.metrics, total: 7, refund_recommended: 3 }, status_breakdown: { pending: 0, validated: 5, manual_review: 1, failed: 1 } } }),
      "GET /api/meta": () => ({ body: meta }),
      "GET /api/requests": () => ({ body: { items: [summary()], total: 1, limit: 8, offset: 0 } }),
    });
    ui();
    expect(screen.getAllByRole("status").length).toBeGreaterThan(0);          // loading placeholders
    expect(screen.queryByTestId("kpi-Total requests")).not.toBeInTheDocument();
    expect(await screen.findByTestId("kpi-Total requests")).toHaveTextContent("7");
    expect(screen.getByTestId("kpi-Refunds recommended")).toHaveTextContent("3");
    expect(screen.getByRole("img", { name: /Validated: 5/ })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "REQ-AAA" })).toHaveAttribute("href", "/requests/REQ-AAA");
  });

  it("shows an empty state with a call to action when nothing exists", async () => {
    mockApi({
      "GET /api/metrics": () => ({ body: emptyMetrics }), "GET /api/meta": () => ({ body: meta }),
      "GET /api/requests": () => ({ body: { items: [], total: 0, limit: 8, offset: 0 } }),
    });
    ui();
    expect(await screen.findByText("No return requests yet")).toBeInTheDocument();
    expect(screen.getByText("No validation failures recorded.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create a return request" })).toBeInTheDocument();
  });

  it("shows the backend error message and retries on request", async () => {
    let ok = false;
    mockApi({
      "GET /api/metrics": () => (ok ? { body: emptyMetrics } : { status: 500, body: { error: { code: "internal_error", message: "Something went wrong on the server." } } }),
      "GET /api/meta": () => ({ body: meta }),
      "GET /api/requests": () => ({ body: { items: [], total: 0, limit: 8, offset: 0 } }),
    });
    ui();
    const alert = await screen.findByText("Metrics could not be loaded");
    expect(alert).toBeInTheDocument();
    expect(screen.getByText("Something went wrong on the server.")).toBeInTheDocument();
    ok = true;
    await userEvent.click(screen.getAllByRole("button", { name: /Try again/ })[0]);
    expect(await screen.findByTestId("kpi-Total requests")).toHaveTextContent("0");
  });

  it("reports an unreachable backend plainly", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    ui();
    expect((await screen.findAllByText(/server could not be reached/i)).length).toBeGreaterThan(0);
  });

  it("sends the search text and status filter to the backend", async () => {
    const calls = mockApi({
      "GET /api/metrics": () => ({ body: emptyMetrics }), "GET /api/meta": () => ({ body: meta }),
      "GET /api/requests": () => ({ body: { items: [], total: 0, limit: 8, offset: 0 } }),
    });
    ui();
    await userEvent.type(screen.getByLabelText("Search recent requests"), "ORD-002");
    await userEvent.selectOptions(screen.getByLabelText("Filter by status"), "failed");
    await waitFor(() => expect(calls.some((c) => c.url.includes("q=ORD-002") && c.url.includes("status=failed"))).toBe(true));
    expect(await screen.findByText("No requests match")).toBeInTheDocument();
  });
});
