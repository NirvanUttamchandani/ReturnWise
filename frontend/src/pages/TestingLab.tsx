import { useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Play, XCircle } from "lucide-react";
import { api, ApiError, type Scenario, type ScenarioResult } from "../lib/api";
import { useAsync } from "../lib/useAsync";
import { Badge, Button, Card, CardHeader, ErrorState, LoadingBlock, Notice, PageHeader } from "../components/ui";

const show = (v: unknown) => (v === null || v === undefined ? "none" : Array.isArray(v) ? v.join(", ") : String(v));

function Result({ r }: { r: ScenarioResult }) {
  return (
    <div className="border-t border-line bg-paper px-5 py-4">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <Badge tone={r.passed ? "ok" : "bad"}>{r.passed ? "All checks passed" : "Some checks failed"}</Badge>
        {r.request_id && <>
          <span className="text-xs text-muted">Saved as test request <span className="font-mono">{r.request_id}</span></span>
          <Link to={`/workflow/${r.request_id}`} className="text-sm font-medium text-teal-700 hover:underline">Open workflow</Link>
          <Link to={`/resolution/${r.request_id}`} className="text-sm font-medium text-teal-700 hover:underline">Open resolution</Link></>}
      </div>
      {r.error && <p className="mb-2 text-sm text-bad">{r.error}</p>}
      <table className="w-full text-left text-sm">
        <caption className="sr-only">Expected versus actual results</caption>
        <thead><tr className="text-xs text-muted"><th scope="col" className="py-1 pr-3 font-medium">Check</th><th scope="col" className="py-1 pr-3 font-medium">Expected</th><th scope="col" className="py-1 pr-3 font-medium">Actual</th><th scope="col" className="py-1 font-medium">Result</th></tr></thead>
        <tbody>{r.checks.map((c) => (
          <tr key={c.check} className="border-t border-line">
            <td className="py-1.5 pr-3">{c.check}</td><td className="num py-1.5 pr-3 font-mono text-xs">{show(c.expected)}</td><td className="num py-1.5 pr-3 font-mono text-xs">{show(c.actual)}</td>
            <td className="py-1.5">{c.passed ? <span className="inline-flex items-center gap-1 text-ok"><CheckCircle2 className="size-4" aria-hidden />Pass</span> : <span className="inline-flex items-center gap-1 text-bad"><XCircle className="size-4" aria-hidden />Fail</span>}</td>
          </tr>))}</tbody>
      </table>
    </div>
  );
}

export default function TestingLab() {
  const list = useAsync(() => api.scenarios(), []);
  const [results, setResults] = useState<Record<string, ScenarioResult>>({});
  const [running, setRunning] = useState<string | null>(null);
  const [failure, setFailure] = useState<ApiError | null>(null);

  async function run(id: string) {
    setRunning(id); setFailure(null);
    try {
      if (id === "all") {
        const r = await api.runAll();
        setResults(Object.fromEntries(r.results.map((x) => [x.id, x])));
      } else {
        const r = await api.runScenario(id);
        setResults((p) => ({ ...p, [id]: r }));
      }
    } catch (e) { setFailure(e instanceof ApiError ? e : new ApiError(0, "unknown", "Scenario could not be run.")); }
    finally { setRunning(null); }
  }

  const done = Object.values(results);
  return (
    <>
      <PageHeader title="Testing Lab" subtitle="Each scenario submits a real request through the real five-agent workflow and compares the stored result with what was expected."
        actions={<Button variant="primary" loading={running === "all"} disabled={!!running && running !== "all"} onClick={() => run("all")}><Play className="size-4" aria-hidden />Run all scenarios</Button>} />
      <div className="mb-4"><Notice tone="info">Runs are saved as test requests and are hidden from the Overview unless you include them. Scenarios marked with a fault deliberately corrupt the Resolution Agent&apos;s draft so you can watch the Critic catch it. That fault can only be triggered here.</Notice></div>
      {failure && <div className="mb-4"><Notice tone="bad" title="Scenario run failed">{failure.message}</Notice></div>}
      {done.length > 0 && <p className="mb-3 text-sm text-muted" data-testid="lab-summary">{done.filter((d) => d.passed).length} of {done.length} scenarios passed in this session.</p>}

      <Card>
        <CardHeader title="Scenarios" hint="Expected results are defined in the backend, not in this page" />
        {list.loading && !list.data ? <LoadingBlock /> : list.error ? <ErrorState error={list.error} onRetry={list.reload} />
          : <ul>{list.data?.scenarios.map((s: Scenario) => (
            <li key={s.id} data-testid={`scenario-${s.id}`}>
              <div className="flex flex-wrap items-center gap-3 border-t border-line px-5 py-3 first:border-t-0">
                <span className="w-14 font-mono text-xs text-muted">{s.id}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-ink">{s.title}</p>
                  <p className="text-xs text-muted">{s.order_id ? `Order ${s.order_id} · ` : ""}{s.reason}{s.fault ? ` · fault: ${s.fault}` : ""}</p>
                </div>
                {results[s.id] && <Badge tone={results[s.id].passed ? "ok" : "bad"}>{results[s.id].passed ? "Passed" : "Failed"}</Badge>}
                <Button loading={running === s.id} disabled={!!running && running !== s.id} onClick={() => run(s.id)} aria-label={`Run scenario ${s.id}`}>Run</Button>
              </div>
              {results[s.id] && <Result r={results[s.id]} />}
            </li>))}</ul>}
      </Card>
    </>
  );
}
