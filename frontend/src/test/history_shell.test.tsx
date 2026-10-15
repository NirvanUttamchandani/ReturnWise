import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import History from "../pages/History";
import AppShell from "../components/AppShell";
import PipelineRail from "../components/PipelineRail";
import { Route, Routes } from "react-router-dom";
import { meta, mockApi, renderAt, summary } from "./helpers";
import type { ExecutionStep } from "../lib/api";

beforeEach(() => vi.unstubAllGlobals());

describe("Request History", () => {
  it("restores filters from the URL after a refresh and sends them to the backend", async () => {
    const calls = mockApi({
      "GET /api/meta": () => ({ body: meta }),
      "GET /api/requests": () => ({ body: { items: [summary({ request_id: "REQ-FAIL1", status: "failed", outcome: { label: "Processing Failed", tone: "bad" } })], total: 1, limit: 15, offset: 0 } }),
    });
    renderAt(<History />, "/requests?status=failed&q=FAKE&tests=1");
    expect(await screen.findByRole("link", { name: "REQ-FAIL1" })).toBeInTheDocument();
    const list = calls.find((c) => c.key === "GET /api/requests")!;
    expect(list.url).toContain("status=failed"); expect(list.url).toContain("q=FAKE"); expect(list.url).toContain("include_tests=true");
    expect(screen.getByLabelText("Filter by status")).toHaveValue("failed");
    expect(screen.getByLabelText("Search requests")).toHaveValue("FAKE");
  });

  it("shows a filtered-empty state with a way to clear filters", async () => {
    mockApi({ "GET /api/meta": () => ({ body: meta }), "GET /api/requests": () => ({ body: { items: [], total: 0, limit: 15, offset: 0 } }) });
    renderAt(<History />, "/requests?status=failed");
    expect(await screen.findByText("No requests match these filters")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    await waitFor(() => expect(screen.getByLabelText("Filter by status")).toHaveValue(""));
  });

  it("pages through results using offset", async () => {
    const calls = mockApi({
      "GET /api/meta": () => ({ body: meta }),
      "GET /api/requests": () => ({ body: { items: [summary()], total: 40, limit: 15, offset: 0 } }),
    });
    renderAt(<History />, "/requests");
    await screen.findByRole("link", { name: "REQ-AAA" });
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(calls.some((c) => c.url.includes("offset=15"))).toBe(true));
  });

  it("shows an error state when the list cannot be loaded", async () => {
    mockApi({ "GET /api/meta": () => ({ body: meta }), "GET /api/requests": () => ({ status: 500, body: { error: { code: "internal_error", message: "Server problem." } } }) });
    renderAt(<History />, "/requests");
    expect(await screen.findByText("Requests could not be loaded")).toBeInTheDocument();
  });
});

describe("Responsive navigation", () => {
  const shell = () => renderAt(<Routes><Route element={<AppShell />}><Route index element={<p>Home</p>} /><Route path="lab" element={<p>Lab page</p>} /></Route></Routes>);

  it("opens the drawer from the menu button, closes with Escape, and closes after navigating", async () => {
    shell();
    const drawer = screen.getByTestId("drawer");
    expect(drawer).toHaveAttribute("hidden");
    await userEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    expect(drawer).not.toHaveAttribute("hidden");
    await userEvent.keyboard("{Escape}");
    expect(drawer).toHaveAttribute("hidden");
    await userEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    await userEvent.click(within(drawer).getByRole("link", { name: "Testing Lab" }));
    expect(await screen.findByText("Lab page")).toBeInTheDocument();
    expect(drawer).toHaveAttribute("hidden");
  });

  it("lists all six sections with no emoji", () => {
    shell();
    const names = ["Overview", "New Return", "Agent Workflow", "Resolution Center", "Request History", "Testing Lab"];
    const side = within(screen.getByTestId("sidebar"));
    names.forEach((n) => expect(side.getByRole("link", { name: n })).toBeInTheDocument());
    expect(screen.getByTestId("sidebar").textContent).not.toMatch(/\p{Extended_Pictographic}/u);
  });
});

const step = (o: Partial<ExecutionStep>): ExecutionStep => ({ execution_order: 1, agent_name: "Intake and Planning Agent", agent_role: "Planner Agent", step_type: "agent", status: "success", verdict: "success",
  input_summary: "in", output_summary: "out", explanation: "ok", executed_at: "2025-02-15T10:00:00+00:00", input: { a: 1 }, output: { b: 2 }, ...o });

describe("PipelineRail", () => {
  it("marks error and skipped stages and selects the failing stage first", () => {
    renderAt(<PipelineRail steps={[step({}), step({ execution_order: 2, agent_name: "Order and Policy Research Agent", status: "error", verdict: null, explanation: "Order not found." }),
      step({ execution_order: 3, status: "skipped", step_type: "skipped", verdict: null }), step({ execution_order: 4, status: "skipped", step_type: "skipped", verdict: null }), step({ execution_order: 5, status: "skipped", step_type: "skipped", verdict: null })]} />);
    expect(screen.getByText("Error")).toBeInTheDocument();
    expect(screen.getAllByText("Skipped")).toHaveLength(3);
    expect(screen.getByRole("region", { name: "Stage details" })).toHaveTextContent("Order not found.");
    expect(screen.queryByLabelText("Correction loop")).not.toBeInTheDocument();
  });

  it("renders the correction loop only when it ran and lets a stage be inspected", async () => {
    const out = { checks_performed: [{ check: "REFUND_AMOUNT_CORRECT", passed: false, detail: "Amount mismatch" }], detected_errors: ["Amount mismatch"] };
    renderAt(<PipelineRail steps={[step({}), step({ execution_order: 2 }), step({ execution_order: 3 }), step({ execution_order: 4 }),
      step({ execution_order: 5, step_type: "validation", verdict: "failed", output: out }),
      step({ execution_order: 6, step_type: "correction", verdict: "refund", agent_name: "Resolution Agent (correction)" }),
      step({ execution_order: 7, step_type: "revalidation", verdict: "passed", agent_name: "Validation Agent (revalidation)" })]} />);
    expect(screen.getByLabelText("Correction loop")).toBeInTheDocument();
    expect(screen.getByText("Critic rejected")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Validation \(Critic\)/ }));
    expect(screen.getByRole("region", { name: "Stage details" })).toHaveTextContent("Amount mismatch");
    expect(screen.getByRole("button", { name: /Validation \(Critic\)/ })).toHaveAttribute("aria-pressed", "true");
  });
});
