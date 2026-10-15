import { useState } from "react";
import { Link } from "react-router-dom";
import { PlusCircle, Search } from "lucide-react";
import { api, type MetricsResponse, type RequestSummary } from "../lib/api";
import { useAsync, useDebounced } from "../lib/useAsync";
import RequestTable from "../components/RequestTable";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, LoadingBlock, PageHeader, inputCls } from "../components/ui";

function Kpi({ label, value, note }: { label: string; value: number; note: string }) {
  return (
    <Card as="div" className="p-4">
      <p className="text-xs text-muted">{label}</p>
      <p className="num mt-1.5 text-2xl font-semibold tracking-tight text-ink" data-testid={`kpi-${label}`}>{value}</p>
      <p className="mt-1 text-xs text-muted">{note}</p>
    </Card>
  );
}

const SEGMENTS = [
  { key: "validated", label: "Validated", color: "bg-teal-600" },
  { key: "manual_review", label: "Manual review", color: "bg-warn" },
  { key: "failed", label: "Processing failed", color: "bg-bad" },
  { key: "pending", label: "In progress", color: "bg-navy-300" },
] as const;

function Breakdown({ m }: { m: MetricsResponse }) {
  const total = m.metrics.total;
  return (
    <Card>
      <CardHeader title="Status breakdown" hint="Final state of each stored request" />
      <div className="p-5">
        {total === 0 ? <p className="text-sm text-muted">No requests yet.</p> : (
          <>
            <div className="flex h-3 overflow-hidden rounded-full bg-idle-bg" role="img"
              aria-label={SEGMENTS.map((s) => `${s.label}: ${m.status_breakdown[s.key]}`).join(", ")}>
              {SEGMENTS.map((s) => m.status_breakdown[s.key] > 0 && (
                <div key={s.key} className={s.color} style={{ width: `${(m.status_breakdown[s.key] / total) * 100}%` }} />))}
            </div>
            <ul className="mt-4 grid grid-cols-2 gap-3 text-sm">
              {SEGMENTS.map((s) => (
                <li key={s.key} className="flex items-center gap-2">
                  <span className={`size-2.5 rounded-full ${s.color}`} aria-hidden />
                  <span className="text-muted">{s.label}</span><span className="num ml-auto font-medium">{m.status_breakdown[s.key]}</span>
                </li>))}
            </ul>
          </>)}
      </div>
    </Card>
  );
}

function Attention({ title, hint, rows, empty }: { title: string; hint: string; rows: RequestSummary[]; empty: string }) {
  return (
    <Card>
      <CardHeader title={title} hint={hint} />
      {rows.length === 0 ? <p className="p-5 text-sm text-muted">{empty}</p> : (
        <ul className="divide-y divide-line">
          {rows.map((r) => (
            <li key={r.request_id} className="flex items-center justify-between gap-3 px-5 py-3 text-sm">
              <div className="min-w-0">
                <Link to={`/requests/${r.request_id}`} className="font-mono text-[13px] font-medium text-teal-700 hover:underline">{r.request_id}</Link>
                <p className="truncate text-xs text-muted">{r.order_id}{r.error_message ? ` · ${r.error_message}` : ""}</p>
              </div>
              <Badge tone={r.outcome.tone}>{r.outcome.label}</Badge>
            </li>))}
        </ul>)}
    </Card>
  );
}

export default function Overview() {
  const [includeTests, setIncludeTests] = useState(false);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const dq = useDebounced(q);
  const metrics = useAsync(() => api.metrics(includeTests), [includeTests]);
  const meta = useAsync(() => api.meta(), []);
  const recent = useAsync(() => api.listRequests({ q: dq, status, include_tests: includeTests, limit: 8 }), [dq, status, includeTests]);

  return (
    <>
      <PageHeader title="Overview" subtitle="Live figures from the stored requests. Every number is read from the database."
        actions={<Link to="/new"><Button variant="primary"><PlusCircle className="size-4" aria-hidden />New return</Button></Link>} />

      <label className="mb-4 flex w-fit items-center gap-2 text-sm text-muted">
        <input type="checkbox" checked={includeTests} onChange={(e) => setIncludeTests(e.target.checked)} className="size-4 accent-teal-600" />
        Include Testing Lab runs
      </label>

      {metrics.loading && !metrics.data ? <Card><LoadingBlock label="Loading metrics" /></Card>
        : metrics.error ? <Card><ErrorState error={metrics.error} onRetry={metrics.reload} title="Metrics could not be loaded" /></Card>
        : metrics.data && (
          <>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
              <Kpi label="Total requests" value={metrics.data.metrics.total} note="All stored requests" />
              <Kpi label="Refunds recommended" value={metrics.data.metrics.refund_recommended} note="Validated, not paid" />
              <Kpi label="Manual review" value={metrics.data.metrics.manual_review} note="Needs a person" />
              <Kpi label="Processing failed" value={metrics.data.metrics.processing_failed} note="No recommendation made" />
              <Kpi label="Critic rejections" value={metrics.data.metrics.validation_failures} note={`${metrics.data.metrics.correction_attempts} correction attempts`} />
            </div>
            <div className="mt-5 grid gap-5 lg:grid-cols-3">
              <Breakdown m={metrics.data} />
              <Attention title="Recent validation failures" hint="Critic rejected the first draft" rows={metrics.data.validation_failures} empty="No validation failures recorded." />
              <Attention title="Manual-review cases" hint="Waiting for a person" rows={metrics.data.manual_review_cases} empty="No cases are waiting for review." />
            </div>
          </>)}

      <Card className="mt-5">
        <CardHeader title="Recent requests" right={<Link to="/requests" className="text-sm font-medium text-teal-700 hover:underline">View all</Link>} />
        <div className="flex flex-wrap gap-3 border-b border-line px-5 py-3">
          <div className="relative min-w-52 flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted" aria-hidden />
            <input aria-label="Search recent requests" placeholder="Search by request or order ID" value={q} onChange={(e) => setQ(e.target.value)} className={`${inputCls()} pl-9`} />
          </div>
          <select aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)} className={`${inputCls()} sm:w-56`}>
            <option value="">All statuses</option>
            {meta.data?.statuses.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </div>
        {recent.loading && !recent.data ? <LoadingBlock label="Loading requests" />
          : recent.error ? <ErrorState error={recent.error} onRetry={recent.reload} title="Requests could not be loaded" />
          : recent.data && recent.data.items.length === 0
            ? (dq || status
              ? <EmptyState title="No requests match" body="Try a different search or clear the status filter." />
              : <EmptyState title="No return requests yet" body="Submit a return to see it processed by the five agents." action={<Link to="/new"><Button variant="primary">Create a return request</Button></Link>} />)
            : recent.data && <RequestTable rows={recent.data.items} />}
      </Card>
    </>
  );
}
